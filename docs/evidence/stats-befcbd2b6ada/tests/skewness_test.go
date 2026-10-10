package stats

import (
	"errors"
	"math"
	"testing"
)

func skewnessApproxEqual(t *testing.T, got, want float64) {
	const eps = 1e-9
	if math.IsNaN(want) {
		if !math.IsNaN(got) {
			t.Fatalf("expected NaN, got %v", got)
		}
		return
	}
	if math.Abs(got-want) > eps {
		t.Fatalf("got %v, want %v (diff %v)", got, want, math.Abs(got-want))
	}
}

func TestSampleSkewness(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"too short", Float64Data{1, 2}, math.NaN(), ErrEmptyInput},
		{"zero variance propagates", Float64Data{3, 3, 3}, math.NaN(), ErrZero},
		{"zero population skew", Float64Data{-1, 0, 1}, 0.0, nil},
		{"adjusted skew", Float64Data{1, 2, 4}, 0.0, nil}, // expected will be computed inside test
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleSkewness(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr != nil {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			// compute expected value
			if tc.name == "zero population skew" {
				skewnessApproxEqual(t, got, 0.0)
				return
			}
			// for "adjusted skew" compute using formula based on PopulationSkewness
			pop, _ := PopulationSkewness(tc.input)
			n := float64(tc.input.Len())
			expected := pop * math.Sqrt(n*(n-1)) / (n - 2)
			skewnessApproxEqual(t, got, expected)
		})
	}
}

func TestSkewness(t *testing.T) {
	input := Float64Data{1, 2, 4}
	got, err := Skewness(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want, err2 := PopulationSkewness(input)
	if err2 != nil {
		t.Fatalf("unexpected error from PopulationSkewness: %v", err2)
	}
	skewnessApproxEqual(t, got, want)
}

func TestPopulationSkewness_Errors(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr error
	}{
		{"empty", Float64Data{}, ErrEmptyInput},
		{"nil", nil, ErrEmptyInput},
		{"single", Float64Data{1.0}, ErrEmptyInput},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationSkewness(tc.data)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !math.IsNaN(got) {
				t.Fatalf("expected NaN result on error, got %v", got)
			}
		})
	}
}

func TestPopulationSkewness_ZeroVariance(t *testing.T) {
	data := Float64Data{5, 5, 5}
	got, err := PopulationSkewness(data)
	if !errors.Is(err, ErrZero) {
		t.Fatalf("expected ErrZero, got %v", err)
	}
	if !math.IsNaN(got) {
		t.Fatalf("expected NaN result on zero variance, got %v", got)
	}
}

func TestPopulationSkewness_ZeroCubes(t *testing.T) {
	data := Float64Data{-1, 0, 1}
	got, err := PopulationSkewness(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 0.0 {
		t.Fatalf("expected 0 result when sum of cubes is zero, got %v", got)
	}
}

func TestPopulationSkewness_Basic(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 10}
	got, err := PopulationSkewness(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// compute expected skewness manually
	mean, _ := Mean(data)
	var sumSq, sumCu float64
	for _, v := range data {
		d := v - mean
		sumSq += d * d
		sumCu += d * d * d
	}
	n := float64(len(data))
	variance := sumSq / n
	stdCubed := math.Pow(variance, 3.0/2.0)
	want := (sumCu / n) / stdCubed
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("unexpected skewness: got %v want %v", got, want)
	}
}
