package stats

import (
	"errors"
	"math"
	"strings"
	"testing"
)

func describeFloatEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestDescribePercentileFunc_EmptyNoNaN(t *testing.T) {
	input := Float64Data{}
	desc, err := DescribePercentileFunc(input, false, nil, Percentile)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if desc == nil {
		t.Fatalf("description is nil")
	}
	if desc.Count != 0 {
		t.Errorf("expected Count 0, got %d", desc.Count)
	}
	if desc.AllowedNaN {
		t.Errorf("expected AllowedNaN false, got true")
	}
}

func TestDescribePercentileFunc_EmptyAllowNaN(t *testing.T) {
	input := Float64Data{}
	desc, err := DescribePercentileFunc(input, true, nil, Percentile)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if desc.Count != 0 {
		t.Errorf("expected Count 0, got %d", desc.Count)
	}
	if !desc.AllowedNaN {
		t.Errorf("expected AllowedNaN true, got false")
	}
	// Statistics on empty data should be NaN
	if !math.IsNaN(desc.Mean) {
		t.Errorf("expected Mean NaN, got %v", desc.Mean)
	}
	if !math.IsNaN(desc.Std) {
		t.Errorf("expected Std NaN, got %v", desc.Std)
	}
	if !math.IsNaN(desc.Max) {
		t.Errorf("expected Max NaN, got %v", desc.Max)
	}
	if !math.IsNaN(desc.Min) {
		t.Errorf("expected Min NaN, got %v", desc.Min)
	}
	if !math.IsNaN(desc.Range) {
		t.Errorf("expected Range NaN, got %v", desc.Range)
	}
}

func TestDescribePercentileFunc_WithPercentiles(t *testing.T) {
	input := Float64Data{1, 2, 3, 4, 5}
	percentiles := []float64{0, 50, 100}
	customFunc := func(data Float64Data, p float64) (float64, error) {
		// simply return the percentile value itself for testing
		return p, nil
	}
	desc, err := DescribePercentileFunc(input, false, &percentiles, customFunc)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(desc.DescriptionPercentiles) != len(percentiles) {
		t.Fatalf("expected %d percentiles, got %d", len(percentiles), len(desc.DescriptionPercentiles))
	}
	for i, dp := range desc.DescriptionPercentiles {
		if !describeFloatEqual(dp.Percentile, percentiles[i]) {
			t.Errorf("percentile order mismatch at %d: got %v want %v", i, dp.Percentile, percentiles[i])
		}
		if !describeFloatEqual(dp.Value, percentiles[i]) {
			t.Errorf("value mismatch for percentile %v: got %v want %v", dp.Percentile, dp.Value, percentiles[i])
		}
	}
}

func TestDescribePercentileFunc_SkipOnError(t *testing.T) {
	input := Float64Data{10, 20, 30}
	percentiles := []float64{25, 75}
	errFunc := func(data Float64Data, p float64) (float64, error) {
		if p == 75 {
			return 0, errors.New("forced error")
		}
		return p, nil
	}
	desc, err := DescribePercentileFunc(input, false, &percentiles, errFunc)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(desc.DescriptionPercentiles) != 1 {
		t.Fatalf("expected 1 successful percentile, got %d", len(desc.DescriptionPercentiles))
	}
	if !describeFloatEqual(desc.DescriptionPercentiles[0].Percentile, 25) {
		t.Errorf("unexpected percentile stored: %v", desc.DescriptionPercentiles[0].Percentile)
	}
}

func TestDescriptionString_Basic(t *testing.T) {
	input := Float64Data{2, 4, 6, 8}
	// Use the real Percentile function for a single percentile to have deterministic values
	perc := []float64{50}
	desc, err := DescribePercentileFunc(input, false, &perc, Percentile)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	s := desc.String(2)
	// Verify presence of each line
	if !strings.Contains(s, "count\t4\n") {
		t.Errorf("output missing count line: %s", s)
	}
	if !strings.Contains(s, "mean\t") {
		t.Errorf("output missing mean line: %s", s)
	}
	if !strings.Contains(s, "std\t") {
		t.Errorf("output missing std line: %s", s)
	}
	if !strings.Contains(s, "max\t") {
		t.Errorf("output missing max line: %s", s)
	}
	if !strings.Contains(s, "min\t") {
		t.Errorf("output missing min line: %s", s)
	}
	if !strings.Contains(s, "range\t") {
		t.Errorf("output missing range line: %s", s)
	}
	if !strings.Contains(s, "50.00%\t") {
		t.Errorf("output missing percentile line: %s", s)
	}
	if !strings.Contains(s, "NaN OK\tfalse") {
		t.Errorf("output missing NaN OK line: %s", s)
	}
}

func TestDescribe_ForwardsToPercentileFunc(t *testing.T) {
	data := Float64Data{5, 10, 15}
	perc := []float64{0, 100}
	// Call Describe (which uses Percentile internally)
	d1, err1 := Describe(data, false, &perc)
	if err1 != nil {
		t.Fatalf("Describe returned error: %v", err1)
	}
	// Call DescribePercentileFunc directly with the same Percentile function
	d2, err2 := DescribePercentileFunc(data, false, &perc, Percentile)
	if err2 != nil {
		t.Fatalf("DescribePercentileFunc returned error: %v", err2)
	}
	if d1.Count != d2.Count || !describeFloatEqual(d1.Mean, d2.Mean) || len(d1.DescriptionPercentiles) != len(d2.DescriptionPercentiles) {
		t.Errorf("Describe result differs from DescribePercentileFunc")
	}
}
