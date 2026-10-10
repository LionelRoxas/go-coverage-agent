package stats

import (
	"errors"
	"math"
	"testing"
)

type weightedMeanCase struct {
	name    string
	data    []float64
	weights []float64
	want    float64
	wantErr error
}

func weightedMeanApproxEqual(got, want float64) bool {
	const eps = 1e-9
	return math.Abs(got-want) <= eps
}

func TestWeightedMean_ErrorsAndEdgeCases(t *testing.T) {
	cases := []weightedMeanCase{
		{
			name:    "empty input",
			data:    []float64{},
			weights: []float64{},
			want:    math.NaN(),
			wantErr: ErrEmptyInput,
		},
		{
			name:    "mismatched lengths",
			data:    []float64{1, 2, 3},
			weights: []float64{1, 2},
			want:    math.NaN(),
			wantErr: ErrSize,
		},
		{
			name:    "negative weight",
			data:    []float64{1, 2},
			weights: []float64{0.5, -1},
			want:    math.NaN(),
			wantErr: ErrNegative,
		},
		{
			name:    "zero total weight",
			data:    []float64{1, 2},
			weights: []float64{0, 0},
			want:    math.NaN(),
			wantErr: ErrZero,
		},
		{
			name:    "normal case",
			data:    []float64{1, 2, 3},
			weights: []float64{2, 0, 1},
			want:    5.0 / 3.0,
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := WeightedMean(Float64Data(tc.data), Float64Data(tc.weights))
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !weightedMeanApproxEqual(got, tc.want) {
				t.Errorf("weighted mean = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_WeightedMean_Delegates(t *testing.T) {
	cases := []weightedMeanCase{
		{
			name:    "empty input",
			data:    []float64{},
			weights: []float64{},
			want:    math.NaN(),
			wantErr: ErrEmptyInput,
		},
		{
			name:    "normal case",
			data:    []float64{4, 5},
			weights: []float64{1, 3},
			want:    19.0 / 4.0,
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).WeightedMean(Float64Data(tc.weights))
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !weightedMeanApproxEqual(got, tc.want) {
				t.Errorf("weighted mean = %v, want %v", got, tc.want)
			}
		})
	}
}
