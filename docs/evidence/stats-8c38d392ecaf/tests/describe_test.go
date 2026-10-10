package stats

import (
	"errors"
	"math"
	"strings"
	"testing"
)

func describeCustomPercentileFunc(input Float64Data, p float64) (float64, error) {
	// Return p*10 for even percentiles, error for odd percentiles
	if int(p)%2 == 0 {
		return p * 10, nil
	}
	return 0, errors.New("percentile error")
}

func TestDescribePercentileFunc_EarlyReturn(t *testing.T) {
	var empty Float64Data
	desc, err := DescribePercentileFunc(empty, false, nil, Percentile)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if desc.Count != 0 {
		t.Errorf("expected Count 0, got %d", desc.Count)
	}
	if desc.AllowedNaN {
		t.Errorf("expected AllowedNaN false")
	}
}

func TestDescribePercentileFunc_AllowNaNEmpty(t *testing.T) {
	var empty Float64Data
	desc, err := DescribePercentileFunc(empty, true, nil, Percentile)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if desc.Count != 0 {
		t.Errorf("expected Count 0, got %d", desc.Count)
	}
	if !desc.AllowedNaN {
		t.Errorf("expected AllowedNaN true")
	}
}

func TestDescriptionString_Format(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	perc := []float64{50}
	desc, err := Describe(data, false, &perc)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	s := desc.String(2)
	checks := []string{"count\t5", "mean\t3.00", "std\t", "max\t5.00", "min\t1.00", "range\t4.00", "50.00%\t3.00", "NaN OK\tfalse"}
	for _, sub := range checks {
		if !strings.Contains(s, sub) {
			t.Errorf("output missing %q, got %s", sub, s)
		}
	}
}

func TestDescribe_Delegates(t *testing.T) {
	data := Float64Data{10, 20, 30}
	perc := []float64{25, 75}
	desc1, err1 := Describe(data, false, &perc)
	if err1 != nil {
		t.Fatalf("Describe error: %v", err1)
	}
	desc2, err2 := DescribePercentileFunc(data, false, &perc, Percentile)
	if err2 != nil {
		t.Fatalf("DescribePercentileFunc error: %v", err2)
	}
	if desc1.Count != desc2.Count || math.Abs(desc1.Mean-desc2.Mean) > 1e-9 || len(desc1.DescriptionPercentiles) != len(desc2.DescriptionPercentiles) {
		t.Errorf("Describe result differs from DescribePercentileFunc")
	}
}
