package stats

import (
	"errors"
	"math"
	"testing"
)

func skewnessApproxEqual(a, b float64) bool {
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= 1e-9
}

func TestPopulationSkewness(t *testing.T) {
	cases := []struct {
		name     string
		input    Float64Data
		wantErr  error
		wantZero bool
		wantNaN  bool
	}{
		{"empty", Float64Data{}, ErrEmptyInput, false, true},
		{"single", Float64Data{1}, ErrEmptyInput, false, true},
		{"constant", Float64Data{5, 5, 5}, ErrZero, false, true},
		{"symmetricZeroCubes", Float64Data{-1, 0, 1}, nil, true, false},
		{"nonZeroSkew", Float64Data{1, 2, 3, 4, 6}, nil, false, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationSkewness(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			if tc.wantZero {
				if got != 0.0 {
					t.Fatalf("expected 0, got %v", got)
				}
				return
			}
			if tc.name == "nonZeroSkew" {
				mean, _ := Mean(tc.input)
				var sumSq, sumCu float64
				for _, v := range tc.input {
					d := v - mean
					sumSq += d * d
					sumCu += d * d * d
				}
				n := float64(len(tc.input))
				variance := sumSq / n
				stdCubed := math.Pow(variance, 3.0/2.0)
				expected := (sumCu / n) / stdCubed
				if !skewnessApproxEqual(got, expected) {
					t.Fatalf("unexpected skewness: got %v, want %v", got, expected)
				}
			}
		})
	}
}

func TestSampleSkewness(t *testing.T) {
	cases := []struct {
		name     string
		input    Float64Data
		wantErr  error
		wantZero bool
	}{
		{"len2", Float64Data{1, 2}, ErrEmptyInput, false},
		{"zeroG1", Float64Data{-1, 0, 1}, nil, true},
		{"constant", Float64Data{5, 5, 5, 5}, ErrZero, false},
		{"adjusted", Float64Data{1, 2, 3, 4, 6}, nil, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleSkewness(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantZero {
				if got != 0.0 {
					t.Fatalf("expected 0, got %v", got)
				}
				return
			}
			if tc.name == "adjusted" {
				g1, err2 := PopulationSkewness(tc.input)
				if err2 != nil {
					t.Fatalf("unexpected error from PopulationSkewness: %v", err2)
				}
				nf := float64(len(tc.input))
				expected := g1 * math.Sqrt(nf*(nf-1)) / (nf - 2)
				if !skewnessApproxEqual(got, expected) {
					t.Fatalf("unexpected adjusted skewness: got %v, want %v", got, expected)
				}
			}
		})
	}
}

func TestSkewness(t *testing.T) {
	input := Float64Data{1, 2, 3, 4, 6}
	got, err := Skewness(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want, err2 := PopulationSkewness(input)
	if err2 != nil {
		t.Fatalf("unexpected error from PopulationSkewness: %v", err2)
	}
	if !skewnessApproxEqual(got, want) {
		t.Fatalf("Skewness mismatch: got %v, want %v", got, want)
	}
}
