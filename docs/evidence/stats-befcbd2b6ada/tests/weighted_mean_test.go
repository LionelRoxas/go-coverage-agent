package stats

import (
	"errors"
	"math"
	"testing"
)

func weightedMeanApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestWeightedMean_ErrorsAndResult(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		weights []float64
		want    float64
		wantErr error
	}{
		{
			name:    "empty input",
			data:    []float64{},
			weights: []float64{},
			want:    math.NaN(),
			wantErr: ErrEmptyInput,
		},
		{
			name:    "size mismatch",
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
			data:    []float64{10, 20},
			weights: []float64{0, 0},
			want:    math.NaN(),
			wantErr: ErrZero,
		},
		{
			name:    "normal case",
			data:    []float64{1, 2, 3},
			weights: []float64{2, 0, 1},
			// weighted mean = (1*2 + 2*0 + 3*1) / (2+0+1) = (2+0+3)/3 = 5/3 ≈ 1.6666666667
			want:    5.0 / 3.0,
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := WeightedMean(tc.data, tc.weights)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !weightedMeanApproxEqual(got, tc.want) {
					t.Fatalf("expected result %v, got %v", tc.want, got)
				}
			} else {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}

func TestFloat64Data_WeightedMean_Method(t *testing.T) {
	// Reuse the same cases as above to verify method forwarding.
	cases := []struct {
		name    string
		data    []float64
		weights []float64
		want    float64
		wantErr error
	}{
		{
			name:    "empty input",
			data:    []float64{},
			weights: []float64{},
			want:    math.NaN(),
			wantErr: ErrEmptyInput,
		},
		{
			name:    "size mismatch",
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
			data:    []float64{10, 20},
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
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.data)
			got, err := f.WeightedMean(tc.weights)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !weightedMeanApproxEqual(got, tc.want) {
					t.Fatalf("expected result %v, got %v", tc.want, got)
				}
			} else {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}
