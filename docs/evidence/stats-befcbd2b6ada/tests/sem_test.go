package stats

import (
	"errors"
	"math"
	"testing"
)

type semCase struct {
	name    string
	input   []float64
	want    float64
	wantErr error
}

func semApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func semSampleStdDev(data []float64) float64 {
	n := float64(len(data))
	if n == 0 {
		return math.NaN()
	}
	var sum float64
	for _, v := range data {
		sum += v
	}
	mean := sum / n
	var sqSum float64
	for _, v := range data {
		diff := v - mean
		sqSum += diff * diff
	}
	// sample variance uses n-1 denominator
	variance := sqSum / (n - 1)
	return math.Sqrt(variance)
}

func TestSEM(t *testing.T) {
	cases := []semCase{
		{
			name:    "empty input",
			input:   []float64{},
			want:    math.NaN(),
			wantErr: ErrEmptyInput,
		},
		{
			name:  "basic case",
			input: []float64{2, 4, 4, 4, 5, 5, 7, 9},
			// expected computed manually: sample sd / sqrt(n)
			// we compute it here to avoid hard‑coding the numeric value.
			want:    0, // placeholder, will be overwritten in test body
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := SEM(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr != nil {
				// when error expected, result should be NaN per implementation
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			// compute expected SEM for non‑error case
			sd := semSampleStdDev(tc.input)
			expected := sd / math.Sqrt(float64(len(tc.input)))
			if !semApproxEqual(got, expected) {
				t.Fatalf("SEM = %v, want %v", got, expected)
			}
		})
	}
}

func TestFloat64Data_SEM(t *testing.T) {
	// reuse the same cases as above to verify method forwarding
	cases := []semCase{
		{
			name:    "empty input",
			input:   []float64{},
			want:    math.NaN(),
			wantErr: ErrEmptyInput,
		},
		{
			name:    "basic case",
			input:   []float64{2, 4, 4, 4, 5, 5, 7, 9},
			want:    0, // placeholder, computed in test body
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.input)
			got, err := f.SEM()
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr != nil {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			sd := semSampleStdDev(tc.input)
			expected := sd / math.Sqrt(float64(len(tc.input)))
			if !semApproxEqual(got, expected) {
				t.Fatalf("Float64Data.SEM = %v, want %v", got, expected)
			}
		})
	}
}
