package stats

import (
	"errors"
	"fmt"
	"math"
	"strings"
	"testing"
)

func TestDescribePercentileFunc_EdgeCases(t *testing.T) {
	// case 1: empty input, allowNaN false
	empty := Float64Data{}
	desc, err := DescribePercentileFunc(empty, false, nil, func(_ Float64Data, _ float64) (float64, error) {
		return 0, nil
	})
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if desc.Count != 0 || desc.AllowedNaN {
		t.Fatalf("unexpected description fields: %+v", desc)
	}

	// case 2: non-empty input, no percentiles
	data := Float64Data{1, 2, 3, 4, 5}
	desc2, err := DescribePercentileFunc(data, false, nil, func(_ Float64Data, _ float64) (float64, error) {
		return 0, nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if desc2.Count != len(data) {
		t.Fatalf("count mismatch")
	}
	if desc2.AllowedNaN {
		t.Fatalf("AllowedNaN should be false")
	}
	m, _ := Mean(data)
	if math.Abs(desc2.Mean-m) > 1e-9 {
		t.Fatalf("mean mismatch: got %v want %v", desc2.Mean, m)
	}

	// case 3: percentiles with mixed errors, allowNaN false
	perc := []float64{25, 50, 75}
	customFunc := func(_ Float64Data, p float64) (float64, error) {
		if p == 50 {
			return 0, fmt.Errorf("forced error")
		}
		return p * 2, nil
	}
	desc3, err := DescribePercentileFunc(data, false, &perc, customFunc)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(desc3.DescriptionPercentiles) != 2 {
		t.Fatalf("expected 2 percentiles, got %d", len(desc3.DescriptionPercentiles))
	}
	for _, dp := range desc3.DescriptionPercentiles {
		if dp.Percentile == 50 {
			t.Fatalf("percentile 50 should have been skipped")
		}
		if dp.Value != dp.Percentile*2 {
			t.Fatalf("unexpected value for percentile %.2f: %v", dp.Percentile, dp.Value)
		}
	}

	// case 4: allowNaN true, errors are ignored
	desc4, err := DescribePercentileFunc(data, true, &perc, customFunc)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !desc4.AllowedNaN {
		t.Fatalf("AllowedNaN should be true")
	}
	if len(desc4.DescriptionPercentiles) != 3 {
		t.Fatalf("expected all 3 percentiles, got %d", len(desc4.DescriptionPercentiles))
	}
}

func TestDescriptionString(t *testing.T) {
	data := Float64Data{10, 20, 30}
	percVals := []float64{0, 100}
	percFunc := func(_ Float64Data, p float64) (float64, error) {
		return p, nil
	}
	desc, err := DescribePercentileFunc(data, false, &percVals, percFunc)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	s := desc.String(2)
	if !strings.Contains(s, fmt.Sprintf("count\t%d\n", len(data))) {
		t.Fatalf("missing count line")
	}
	if !strings.Contains(s, "NaN OK\tfalse") {
		t.Fatalf("missing NaN OK line")
	}
	for _, p := range percVals {
		line := fmt.Sprintf("%.2f%%\t%.*f\n", p, 2, p)
		if !strings.Contains(s, line) {
			t.Fatalf("missing percentile line: %q", line)
		}
	}
}

func TestDescribe(t *testing.T) {
	data := Float64Data{5, 15, 25}
	perc := []float64{50}
	d1, err1 := Describe(data, false, &perc)
	if err1 != nil {
		t.Fatalf("Describe returned error: %v", err1)
	}
	d2, err2 := DescribePercentileFunc(data, false, &perc, Percentile)
	if err2 != nil {
		t.Fatalf("DescribePercentileFunc returned error: %v", err2)
	}
	if d1.Count != d2.Count || d1.AllowedNaN != d2.AllowedNaN {
		t.Fatalf("Describe result differs from DescribePercentileFunc")
	}
}
