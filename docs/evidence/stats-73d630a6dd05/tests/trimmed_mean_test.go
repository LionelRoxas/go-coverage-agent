package stats

import (
	"errors"
	"math"
	"testing"
)

func TestTrimmedMean_ErrorsAndValues(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 0.0, math.NaN(), ErrEmptyInput},
		{"percent negative", Float64Data{1, 2, 3}, -0.1, math.NaN(), ErrBounds},
		{"percent too large", Float64Data{1, 2, 3}, 0.5, math.NaN(), ErrBounds},
		{"percent NaN", Float64Data{1, 2, 3}, math.NaN(), math.NaN(), ErrBounds},
		{"no trim", Float64Data{1, 2, 3, 4}, 0.0, 2.5, nil},
		{"trim 10%", Float64Data{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, 0.1, 5.5, nil},
		{"single element", Float64Data{42}, 0.0, 42, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := TrimmedMean(tc.input, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if math.IsNaN(tc.want) {
					if !math.IsNaN(got) {
						t.Fatalf("expected NaN, got %v", got)
					}
				} else {
					if math.Abs(got-tc.want) > 1e-9 {
						t.Fatalf("expected %v, got %v", tc.want, got)
					}
				}
			}
		})
	}
}

func TestFloat64Data_TrimmedMean_Method(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
	got, err := data.TrimmedMean(0.1)
	if err != nil {
		t.Fatalf("unexpected error %v", err)
	}
	if math.Abs(got-5.5) > 1e-9 {
		t.Fatalf("expected 5.5, got %v", got)
	}
	// also verify error propagation for empty input
	_, err = Float64Data{}.TrimmedMean(0.0)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput for empty slice, got %v", err)
	}
}
