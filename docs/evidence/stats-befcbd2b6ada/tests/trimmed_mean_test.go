package stats

import (
	"errors"
	"math"
	"testing"
)

func trimmedMeanApproxEqual(t *testing.T, got, want float64) {
	const eps = 1e-9
	if math.IsNaN(want) {
		if !math.IsNaN(got) {
			t.Fatalf("expected NaN, got %v", got)
		}
		return
	}
	if math.Abs(got-want) > eps {
		t.Fatalf("got %v, want %v (diff %v)", got, want, math.Abs(got-want))
	}
}

func TestTrimmedMean(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		percent float64
		want    float64
		wantErr error
	}{
		{"EmptyInput", []float64{}, 0.1, math.NaN(), ErrEmptyInput},
		{"PercentNegative", []float64{1, 2, 3}, -0.1, math.NaN(), ErrBounds},
		{"PercentTooLarge", []float64{1, 2, 3}, 0.5, math.NaN(), ErrBounds},
		{"PercentNaN", []float64{1, 2, 3}, math.NaN(), math.NaN(), ErrBounds},
		{"NoTrim", []float64{1, 2, 3, 4, 5}, 0, 3, nil},
		{"Trim20Percent", []float64{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, 0.2, 5.5, nil},
		{"TrimSmallKZero", []float64{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, 0.09, 5.5, nil},
		{"TrimToOne", []float64{10, 20, 30, 40, 50}, 0.4, 30, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := TrimmedMean(Float64Data(tc.input), tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				trimmedMeanApproxEqual(t, got, tc.want)
			} else {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}

func TestFloat64Data_TrimmedMean(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		percent float64
		want    float64
		wantErr error
	}{
		{"EmptyInput", []float64{}, 0.1, math.NaN(), ErrEmptyInput},
		{"PercentNegative", []float64{1, 2, 3}, -0.1, math.NaN(), ErrBounds},
		{"NoTrim", []float64{1, 2, 3, 4, 5}, 0, 3, nil},
		{"Trim20Percent", []float64{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}, 0.2, 5.5, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			data := Float64Data(tc.input)
			got, err := data.TrimmedMean(tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				trimmedMeanApproxEqual(t, got, tc.want)
			} else {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}
