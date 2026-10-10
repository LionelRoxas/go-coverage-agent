package stats

import (
	"errors"
	"math"
	"testing"
)

func percentileFloatEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	if math.IsInf(got, 0) && math.IsInf(want, 0) {
		return math.Signbit(got) == math.Signbit(want)
	}
	return math.Abs(got-want) <= eps
}

func TestPercentile(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
		wantNaN bool
		wantInf bool
	}{
		{"empty input", Float64Data{}, 50, math.NaN(), EmptyInputErr, true, false},
		{"percent out of bounds (negative)", Float64Data{1, 2, 3}, -10, math.NaN(), BoundsErr, true, false},
		{"percent out of bounds (zero)", Float64Data{1, 2, 3}, 0, math.NaN(), BoundsErr, true, false},
		{"percent out of bounds (>100)", Float64Data{1, 2, 3}, 150, math.NaN(), BoundsErr, true, false},
		{"single element", Float64Data{42}, 75, 42, nil, false, false},
		{"finite interpolation", Float64Data{4, 1, 3, 2}, 25, 1.75, nil, false, false},
		{"duplicate values no interpolation", Float64Data{5, 5, 5, 10}, 25, 5, nil, false, false},
		{"infinite delta", Float64Data{1, math.Inf(1)}, 50, math.Inf(1), nil, false, true},
		{"percent 100 returns max", Float64Data{7, 3, 9, 2}, 100, 9, nil, false, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Percentile(tc.input, tc.percent)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			if tc.wantInf {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
				return
			}
			if !percentileFloatEqual(got, tc.want) {
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
		{"percent out of bounds (negative)", Float64Data{1, 2, 3}, -5, math.NaN(), BoundsErr},
		{"percent out of bounds (>100)", Float64Data{1, 2, 3}, 120, math.NaN(), BoundsErr},
		{"percent 100 returns last", Float64Data{3, 1, 4, 2}, 100, 4, nil},
		{"percent 0 returns first", Float64Data{8, 5, 6}, 0, 5, nil},
		{"normal nearest rank", Float64Data{10, 30, 20, 40}, 25, 20, nil}, // sorted -> [10,20,30,40]; ceil(4*25/100)=1 => index 0 => 10? Wait compute: il=4, percent=25 => ceil(4*0.25)=ceil(1)=1 => or=1 => return c[0]=10. Adjust expected.
	}
	// Fix expected for normal case
	cases[5].want = 10
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileNearestRank(tc.input, tc.percent)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !percentileFloatEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
