package stats

import (
	"errors"
	"math"
	"testing"
)

func kurtosisFloatApproxEqual(t *testing.T, got, want float64) {
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("float mismatch: got %v want %v", got, want)
	}
}

func TestPopulationKurtosis_EdgeCases(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  float64
		err   error
	}{
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"single", Float64Data{1.0}, math.NaN(), ErrEmptyInput},
		{"all equal", Float64Data{5, 5, 5, 5}, math.NaN(), ErrZero},
		{"simple", Float64Data{-1, 0, 1}, -1.5, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationKurtosis(tc.input)
			if !errors.Is(err, tc.err) {
				t.Fatalf("unexpected error: got %v want %v", err, tc.err)
			}
			if tc.err == nil {
				kurtosisFloatApproxEqual(t, got, tc.want)
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}

func TestSampleKurtosis_EdgeCases(t *testing.T) {
	// Helper to compute bias‑corrected expectation using the formula from the source.
	biasCorrect := func(g2 float64, n int) float64 {
		nf := float64(n)
		return ((nf+1)*g2 + 6) * (nf - 1) / ((nf - 2) * (nf - 3))
	}

	cases := []struct {
		name  string
		input Float64Data
		want  float64
		err   error
	}{
		{"too short", Float64Data{1, 2, 3}, math.NaN(), ErrEmptyInput},
		{"all equal", Float64Data{2, 2, 2, 2}, math.NaN(), ErrZero},
		{"normal case", Float64Data{-2, -1, 0, 1, 2}, 0, nil}, // expected will be computed
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleKurtosis(tc.input)
			if !errors.Is(err, tc.err) {
				t.Fatalf("unexpected error: got %v want %v", err, tc.err)
			}
			if tc.err == nil {
				// compute expected using PopulationKurtosis then bias correction
				pop, popErr := PopulationKurtosis(tc.input)
				if popErr != nil {
					t.Fatalf("unexpected error from PopulationKurtosis: %v", popErr)
				}
				expected := biasCorrect(pop, tc.input.Len())
				kurtosisFloatApproxEqual(t, got, expected)
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}

func TestKurtosis_Forward(t *testing.T) {
	data := Float64Data{-1, 0, 1}
	want, err := PopulationKurtosis(data)
	if err != nil {
		t.Fatalf("PopulationKurtosis error: %v", err)
	}
	got, err := Kurtosis(data)
	if err != nil {
		t.Fatalf("Kurtosis error: %v", err)
	}
	kurtosisFloatApproxEqual(t, got, want)
}

func TestFloat64Data_Kurtosis_Method(t *testing.T) {
	data := Float64Data{-1, 0, 1}
	want, err := Kurtosis(data)
	if err != nil {
		t.Fatalf("Kurtosis error: %v", err)
	}
	got, err := data.Kurtosis()
	if err != nil {
		t.Fatalf("Float64Data.Kurtosis error: %v", err)
	}
	kurtosisFloatApproxEqual(t, got, want)
}

func TestFloat64Data_PopulationKurtosis_Method(t *testing.T) {
	data := Float64Data{-1, 0, 1}
	want, err := PopulationKurtosis(data)
	if err != nil {
		t.Fatalf("PopulationKurtosis error: %v", err)
	}
	got, err := data.PopulationKurtosis()
	if err != nil {
		t.Fatalf("Float64Data.PopulationKurtosis error: %v", err)
	}
	kurtosisFloatApproxEqual(t, got, want)
}
