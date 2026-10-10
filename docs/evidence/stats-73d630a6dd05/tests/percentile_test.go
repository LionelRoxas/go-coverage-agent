package stats

import (
	"errors"
	"math"
	"testing"
)

func percentileApproxEqual(a, b float64) bool {
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= 1e-9
}

func TestPercentile(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 50, math.NaN(), EmptyInputErr},
		{"percent zero", Float64Data{1, 2}, 0, math.NaN(), BoundsErr},
		{"percent over 100", Float64Data{1, 2}, 101, math.NaN(), BoundsErr},
		{"single element", Float64Data{42}, 25, 42, nil},
		{"exact rank", Float64Data{5, 1, 3, 2, 4}, 50, 3, nil},
		{"interpolation", Float64Data{10, 20, 30, 40}, 25, 17.5, nil},
		{"infinite delta", Float64Data{-math.MaxFloat64, math.MaxFloat64}, 50, 0, nil},
		{"duplicate values", Float64Data{5, 5, 5, 5}, 30, 5, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Percentile(tc.input, tc.percent)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !percentileApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestPercentileNearestRank(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 50, math.NaN(), EmptyInputErr},
		{"percent NaN", Float64Data{1, 2}, math.NaN(), math.NaN(), BoundsErr},
		{"percent negative", Float64Data{1, 2}, -5, math.NaN(), BoundsErr},
		{"percent over 100", Float64Data{1, 2}, 150, math.NaN(), BoundsErr},
		{"percent 100 returns last", Float64Data{3, 1, 2}, 100, 3, nil},
		{"percent 0 returns first", Float64Data{3, 1, 2}, 0, 1, nil},
		{"normal case", Float64Data{5, 1, 4, 2, 3}, 40, 2, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileNearestRank(tc.input, tc.percent)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !percentileApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
