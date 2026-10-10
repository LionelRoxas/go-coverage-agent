package stats

import (
	"errors"
	"math"
	"testing"
)

func percentileWeightedApproxEqual(got, want float64) bool {
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= 1e-9
}

func TestPercentileWeighted_Errors(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		weights []float64
		percent float64
		wantErr error
	}{
		{"EmptyInput", []float64{}, []float64{}, 50, ErrEmptyInput},
		{"SizeMismatch", []float64{1, 2}, []float64{1}, 50, ErrSize},
		{"PercentZero", []float64{1}, []float64{1}, 0, ErrBounds},
		{"PercentOver", []float64{1}, []float64{1}, 101, ErrBounds},
		{"PercentNaN", []float64{1}, []float64{1}, math.NaN(), ErrBounds},
		{"NegativeWeight", []float64{1, 2}, []float64{-1, 1}, 50, ErrNegative},
		{"ZeroTotalWeight", []float64{1, 2}, []float64{0, 0}, 50, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := PercentileWeighted(Float64Data(tc.data), Float64Data(tc.weights), tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestPercentileWeighted_Normal(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		weights []float64
		percent float64
		want    float64
	}{
		{
			name:    "SimpleSorted",
			data:    []float64{10, 20, 30},
			weights: []float64{1, 2, 1},
			percent: 50,
			want:    20,
		},
		{
			name:    "UnsortedInput",
			data:    []float64{30, 10, 20},
			weights: []float64{1, 1, 2},
			percent: 50,
			want:    20,
		},
		{
			name:    "QuarterPercent",
			data:    []float64{10, 20, 30},
			weights: []float64{1, 2, 1},
			percent: 25,
			want:    10,
		},
		{
			name:    "ThreeQuarterPercent",
			data:    []float64{10, 20, 30},
			weights: []float64{1, 2, 1},
			percent: 75,
			want:    20,
		},
		{
			name:    "NearMaxPercent",
			data:    []float64{10, 20, 30},
			weights: []float64{1, 2, 1},
			percent: 99,
			want:    30,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileWeighted(Float64Data(tc.data), Float64Data(tc.weights), tc.percent)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !percentileWeightedApproxEqual(got, tc.want) {
				t.Fatalf("percentile = %v, want %v", got, tc.want)
			}
		})
	}
}
