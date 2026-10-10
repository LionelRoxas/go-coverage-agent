package stats

import (
	"errors"
	"math"
	"testing"
)

func TestPercentileWeighted_Errors(t *testing.T) {
	tolerance := 1e-9
	cases := []struct {
		name    string
		data    Float64Data
		weights Float64Data
		percent float64
		wantErr error
	}{
		{
			name:    "empty input",
			data:    Float64Data{},
			weights: Float64Data{},
			percent: 50,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "size mismatch",
			data:    Float64Data{1, 2},
			weights: Float64Data{1},
			percent: 50,
			wantErr: ErrSize,
		},
		{
			name:    "percent zero",
			data:    Float64Data{1},
			weights: Float64Data{1},
			percent: 0,
			wantErr: ErrBounds,
		},
		{
			name:    "percent over 100",
			data:    Float64Data{1},
			weights: Float64Data{1},
			percent: 101,
			wantErr: ErrBounds,
		},
		{
			name:    "percent NaN",
			data:    Float64Data{1},
			weights: Float64Data{1},
			percent: math.NaN(),
			wantErr: ErrBounds,
		},
		{
			name:    "negative weight",
			data:    Float64Data{1, 2},
			weights: Float64Data{-1, 1},
			percent: 50,
			wantErr: ErrNegative,
		},
		{
			name:    "zero total weight",
			data:    Float64Data{1, 2},
			weights: Float64Data{0, 0},
			percent: 50,
			wantErr: ErrBounds,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileWeighted(tc.data, tc.weights, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err == nil && (math.IsNaN(got) && !math.IsNaN(got)) {
				t.Fatalf("expected NaN result when error is nil, got %v", got)
			}
			// When an error is expected, the returned value should be NaN per implementation.
			if err != nil && !math.IsNaN(got) {
				t.Errorf("expected NaN result on error, got %v", got)
			}
			// sanity check: result is within data range when no error (not applicable here)
			if err == nil {
				// verify result is within min/max of data
				min, max := tc.data[0], tc.data[0]
				for _, v := range tc.data {
					if v < min {
						min = v
					}
					if v > max {
						max = v
					}
				}
				if got < min-tolerance || got > max+tolerance {
					t.Errorf("result %v out of data bounds [%v,%v]", got, min, max)
				}
			}
		})
	}
}

func TestPercentileWeighted_Result(t *testing.T) {
	tolerance := 1e-9
	cases := []struct {
		name    string
		data    Float64Data
		weights Float64Data
		percent float64
		want    float64
	}{
		{
			name:    "simple equal weights",
			data:    Float64Data{1, 2, 3},
			weights: Float64Data{1, 1, 1},
			percent: 50,
			want:    2,
		},
		{
			name:    "unsorted data with varying weights",
			data:    Float64Data{10, 5, 20},
			weights: Float64Data{2, 5, 3},
			percent: 40,
			// totalWeight = 10, target = 4.0
			// sorted pairs: (5,5), (10,2), (20,3)
			// cum after first =5 >=4 => result 5
			want: 5,
		},
		{
			name:    "percent near 100",
			data:    Float64Data{1, 2, 3, 4},
			weights: Float64Data{1, 1, 1, 1},
			percent: 99,
			// target = 0.99*4 = 3.96, cum reaches 4 at last element => result 4
			want: 4,
		},
		{
			name:    "single element",
			data:    Float64Data{42},
			weights: Float64Data{7},
			percent: 10,
			want:    42,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileWeighted(tc.data, tc.weights, tc.percent)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > tolerance {
				t.Errorf("percentile = %v, want %v", got, tc.want)
			}
		})
	}
}
