package stats

import (
	"errors"
	"math"
	"testing"
)

func TestPercentileWeighted_Errors(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		weights Float64Data
		percent float64
		wantErr error
	}{
		{"empty input", Float64Data{}, Float64Data{}, 50, ErrEmptyInput},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, 50, ErrSize},
		{"percent zero", Float64Data{1}, Float64Data{1}, 0, ErrBounds},
		{"percent over", Float64Data{1}, Float64Data{1}, 101, ErrBounds},
		{"percent NaN", Float64Data{1}, Float64Data{1}, math.NaN(), ErrBounds},
		{"negative weight", Float64Data{1, 2}, Float64Data{-1, 1}, 50, ErrNegative},
		{"zero total weight", Float64Data{1, 2}, Float64Data{0, 0}, 50, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileWeighted(tc.data, tc.weights, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !math.IsNaN(got) {
				t.Fatalf("expected NaN result on error, got %v", got)
			}
		})
	}
}

func TestPercentileWeighted_Normal(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		weights Float64Data
		percent float64
		want    float64
	}{
		{"sorted data 50th", Float64Data{10, 20, 30}, Float64Data{1, 2, 3}, 50, 20},
		{"unsorted data 50th", Float64Data{30, 10, 20}, Float64Data{3, 1, 2}, 50, 20},
		{"percent 100", Float64Data{10, 20, 30}, Float64Data{1, 2, 3}, 100, 30},
		{"percent 34", Float64Data{5, 15, 25}, Float64Data{1, 1, 1}, 34, 15},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileWeighted(tc.data, tc.weights, tc.percent)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsNaN(got) && !math.IsNaN(tc.want) {
				t.Fatalf("got NaN, want %v", tc.want)
			}
			if !math.IsNaN(got) && math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}
