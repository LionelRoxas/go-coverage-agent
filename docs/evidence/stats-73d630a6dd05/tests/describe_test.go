package stats

import (
	"errors"
	"math"
	"strings"
	"testing"
)

func describeMockPercentile(input Float64Data, p float64) (float64, error) {
	// deterministic value for testing, ignore input content
	return p * 2, nil
}

func TestDescribePercentileFunc_EmptyNoNaN(t *testing.T) {
	input := Float64Data{}
	desc, err := DescribePercentileFunc(input, false, nil, describeMockPercentile)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if desc.Count != 0 {
		t.Fatalf("expected count 0, got %d", desc.Count)
	}
	if desc.AllowedNaN {
		t.Fatalf("expected AllowedNaN false")
	}
	if len(desc.DescriptionPercentiles) != 0 {
		t.Fatalf("expected no percentiles, got %d", len(desc.DescriptionPercentiles))
	}
}

func TestDescribePercentileFunc_EmptyAllowNaN_WithPercentiles(t *testing.T) {
	input := Float64Data{}
	pcts := []float64{25, 50}
	desc, err := DescribePercentileFunc(input, true, &pcts, describeMockPercentile)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if desc.Count != 0 {
		t.Fatalf("expected count 0, got %d", desc.Count)
	}
	if !desc.AllowedNaN {
		t.Fatalf("expected AllowedNaN true")
	}
	if len(desc.DescriptionPercentiles) != len(pcts) {
		t.Fatalf("expected %d percentiles, got %d", len(pcts), len(desc.DescriptionPercentiles))
	}
	for i, dp := range desc.DescriptionPercentiles {
		expected := pcts[i] * 2
		if math.Abs(dp.Value-expected) > 1e-9 {
			t.Fatalf("percentile %v value = %v, want %v", dp.Percentile, dp.Value, expected)
		}
	}
}

func TestDescribePercentileFunc_NonEmpty_Mixed(t *testing.T) {
	input := Float64Data{1, 2, 3, 4}
	percents := []float64{0, 100}
	mixedFunc := func(data Float64Data, p float64) (float64, error) {
		if p == 100 {
			return 0, errors.New("bad")
		}
		return p, nil
	}
	desc, err := DescribePercentileFunc(input, false, &percents, mixedFunc)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if desc.Count != len(input) {
		t.Fatalf("count mismatch: got %d want %d", desc.Count, len(input))
	}
	if len(desc.DescriptionPercentiles) != 1 {
		t.Fatalf("expected only 1 successful percentile, got %d", len(desc.DescriptionPercentiles))
	}
	if desc.DescriptionPercentiles[0].Percentile != 0 {
		t.Fatalf("unexpected percentile stored: %v", desc.DescriptionPercentiles[0].Percentile)
	}
	if math.Abs(desc.DescriptionPercentiles[0].Value-0) > 1e-9 {
		t.Fatalf("unexpected value for percentile 0: %v", desc.DescriptionPercentiles[0].Value)
	}
}

func TestDescriptionString(t *testing.T) {
	d := Description{
		Count:                  3,
		Mean:                   2.5,
		Std:                    1.2,
		Max:                    5.0,
		Min:                    0.0,
		Range:                  5.0,
		AllowedNaN:             false,
		DescriptionPercentiles: []descriptionPercentile{{Percentile: 25, Value: 1.0}, {Percentile: 75, Value: 4.0}},
	}
	s := d.String(2)
	checks := []string{
		"count\t3\n",
		"mean\t2.50\n",
		"std\t1.20\n",
		"max\t5.00\n",
		"min\t0.00\n",
		"range\t5.00\n",
		"25.00%\t1.00\n",
		"75.00%\t4.00\n",
		"NaN OK\tfalse",
	}
	for _, sub := range checks {
		if !strings.Contains(s, sub) {
			t.Fatalf("output missing expected substring %q; got %q", sub, s)
		}
	}
}

func TestDescribe_Wrapper(t *testing.T) {
	empty := Float64Data{}
	_, err := Describe(empty, false, nil)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput for empty input, got %v", err)
	}
	data := Float64Data{10, 20, 30}
	desc, err := Describe(data, false, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if desc.Count != len(data) {
		t.Fatalf("expected count %d, got %d", len(data), desc.Count)
	}
}
