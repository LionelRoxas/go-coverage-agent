package stats

import (
	"errors"
	"math"
	"testing"
)

func TestPercentileWeighted_EdgeCases(t *testing.T) {
	type testCase struct {
		name    string
		data    []float64
		weights []float64
		percent float64
		want    float64
		wantErr error
	}

	cases := []testCase{
		{
			name:    "empty input returns ErrEmptyInput",
			data:    []float64{},
			weights: []float64{},
			percent: 50,
			want:    math.NaN(),
			wantErr: ErrEmptyInput,
		},
		{
			name:    "mismatched lengths returns ErrSize",
			data:    []float64{1, 2, 3},
			weights: []float64{1, 2},
			percent: 50,
			want:    math.NaN(),
			wantErr: ErrSize,
		},
		{
			name:    "percent zero returns ErrBounds",
			data:    []float64{1, 2, 3},
			weights: []float64{1, 1, 1},
			percent: 0,
			want:    math.NaN(),
			wantErr: ErrBounds,
		},
		{
			name:    "percent >100 returns ErrBounds",
			data:    []float64{1, 2, 3},
			weights: []float64{1, 1, 1},
			percent: 101,
			want:    math.NaN(),
			wantErr: ErrBounds,
		},
		{
			name:    "percent NaN returns ErrBounds",
			data:    []float64{1, 2, 3},
			weights: []float64{1, 1, 1},
			percent: math.NaN(),
			want:    math.NaN(),
			wantErr: ErrBounds,
		},
		{
			name:    "negative weight returns ErrNegative",
			data:    []float64{1, 2, 3},
			weights: []float64{1, -1, 1},
			percent: 50,
			want:    math.NaN(),
			wantErr: ErrNegative,
		},
		{
			name:    "zero total weight returns ErrBounds",
			data:    []float64{1, 2, 3},
			weights: []float64{0, 0, 0},
			percent: 50,
			want:    math.NaN(),
			wantErr: ErrBounds,
		},
		{
			name:    "basic percentile with sorted data",
			data:    []float64{10, 20, 30},
			weights: []float64{1, 1, 1},
			percent: 50,
			want:    20,
			wantErr: nil,
		},
		{
			name:    "unsorted data gets sorted internally",
			data:    []float64{30, 10, 20},
			weights: []float64{1, 1, 1},
			percent: 50,
			want:    20,
			wantErr: nil,
		},
		{
			name:    "percentile with zero weights except one",
			data:    []float64{5, 10, 15},
			weights: []float64{0, 5, 0},
			percent: 10,
			want:    10,
			wantErr: nil,
		},
		{
			name:    "percent=100 returns max value",
			data:    []float64{1, 2, 3},
			weights: []float64{1, 1, 1},
			percent: 100,
			want:    3,
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentileWeighted(Float64Data(tc.data), Float64Data(tc.weights), tc.percent)
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}
