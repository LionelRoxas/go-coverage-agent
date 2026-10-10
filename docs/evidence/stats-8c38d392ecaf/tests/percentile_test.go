package stats

import (
	"errors"
	"math"
	"testing"
)

func percentileApproxEqual(t *testing.T, got, want float64) {
	if math.IsNaN(want) {
		if !math.IsNaN(got) {
			t.Errorf("expected NaN, got %v", got)
		}
		return
	}
	if math.IsInf(want, 0) {
		if !math.IsInf(got, 0) || math.Signbit(got) != math.Signbit(want) {
			t.Errorf("expected %v, got %v", want, got)
		}
		return
	}
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("got %v, want %v", got, want)
	}
}

func TestPercentile_ErrorsAndEdgeCases(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
	}{
		{"empty slice", Float64Data{}, 50, math.NaN(), EmptyInputErr},
		{"percent NaN", Float64Data{1, 2}, math.NaN(), math.NaN(), BoundsErr},
		{"percent zero", Float64Data{1, 2}, 0, math.NaN(), BoundsErr},
		{"percent over 100", Float64Data{1, 2}, 101, math.NaN(), BoundsErr},
		{"single element", Float64Data{42}, 25, 42, nil},
		{"integer rank", Float64Data{3, 1, 2}, 50, 2, nil},
		{"normal interpolation", Float64Data{5, 1, 3}, 25, 2, nil},
		{"infinite delta", Float64Data{1, math.Inf(1)}, 50, math.Inf(1), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Percentile(tc.input, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				percentileApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestPercentileNearestRank_ErrorsAndEdgeCases(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    float64
		wantErr error
	}{
		{"empty slice", Float64Data{}, 50, math.NaN(), EmptyInputErr},
		{"percent NaN", Float64Data{1, 2}, math.NaN(), math.NaN(), BoundsErr},
		{"percent negative", Float64Data{1, 2}, -5, math.NaN(), BoundsErr},
		{"percent over 100", Float64Data{1, 2}, 150, math.NaN(), BoundsErr},
		{"percent 100 returns max", Float64Data{2, 1, 3}, 100, 3, nil},
		{"percent 0 returns min", Float64Data{5, 2, 9}, 0, 2, nil},
		{"normal rank", Float64Data{10, 30, 20, 40, 50}, 40, 20, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileNearestRank(tc.input, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				percentileApproxEqual(t, got, tc.want)
			}
		})
	}
}
