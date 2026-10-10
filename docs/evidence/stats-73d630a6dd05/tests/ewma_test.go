package stats

import (
	"errors"
	"math"
	"testing"
)

func ewmaManual(input []float64, alpha float64) []float64 {
	if len(input) == 0 {
		return nil
	}
	out := make([]float64, len(input))
	out[0] = input[0]
	for i := 1; i < len(input); i++ {
		out[i] = alpha*input[i] + (1-alpha)*out[i-1]
	}
	return out
}

func ewmaApproxEqual(a, b []float64, tol float64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if math.IsNaN(a[i]) && math.IsNaN(b[i]) {
			continue
		}
		if math.Abs(a[i]-b[i]) > tol {
			return false
		}
	}
	return true
}

func TestEWMA_ErrorsAndValues(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		alpha   float64
		want    []float64
		wantErr error
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			alpha:   0.5,
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "alpha zero",
			input:   Float64Data{1, 2, 3},
			alpha:   0.0,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "alpha negative",
			input:   Float64Data{1, 2, 3},
			alpha:   -0.2,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "alpha greater than one",
			input:   Float64Data{1, 2, 3},
			alpha:   1.5,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "alpha one returns input",
			input:   Float64Data{10, 20, 30},
			alpha:   1.0,
			want:    []float64{10, 20, 30},
			wantErr: nil,
		},
		{
			name:    "typical alpha",
			input:   Float64Data{1, 2, 3, 4},
			alpha:   0.5,
			want:    ewmaManual([]float64{1, 2, 3, 4}, 0.5),
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := EWMA(tc.input, tc.alpha)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !ewmaApproxEqual(got, tc.want, 1e-9) {
					t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
				}
			}
		})
	}
}

func TestFloat64Data_EWMA_Delegates(t *testing.T) {
	input := Float64Data{5, 10, 15}
	alpha := 0.3
	got1, err1 := EWMA(input, alpha)
	got2, err2 := input.EWMA(alpha)
	if err1 != err2 {
		t.Fatalf("different errors: %v vs %v", err1, err2)
	}
	if err1 == nil && !ewmaApproxEqual(got1, got2, 1e-9) {
		t.Fatalf("method and function differ: %v vs %v", got1, got2)
	}
}
