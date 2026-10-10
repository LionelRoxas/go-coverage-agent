package stats

import (
	"errors"
	"math"
	"testing"
)

func skewnessApproxEqual(t *testing.T, got, want float64) {
	t.Helper()
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > eps {
		t.Fatalf("approx equal failed: got %v, want %v", got, want)
	}
}

func TestPopulationSkewness_EdgeCases(t *testing.T) {
	cases := []struct {
		name        string
		data        Float64Data
		wantErr     error
		wantNaN     bool
		wantZero    bool
		wantPosSign bool
		wantNegSign bool
	}{
		{"empty", Float64Data{}, ErrEmptyInput, true, false, false, false},
		{"single", Float64Data{1}, ErrEmptyInput, true, false, false, false},
		{"zero variance", Float64Data{5, 5, 5}, ErrZero, true, false, false, false},
		{"zero cubes", Float64Data{-1, 0, 1}, nil, false, true, false, false},
		{"positive skew", Float64Data{1, 1, 1, 2, 10}, nil, false, false, true, false},
		{"negative skew", Float64Data{-10, -2, -1, -1, -1}, nil, false, false, false, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationSkewness(tc.data)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !tc.wantNaN || !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantZero {
				if got != 0.0 {
					t.Fatalf("expected zero result, got %v", got)
				}
				return
			}
			if tc.wantPosSign && !(got > 0) {
				t.Fatalf("expected positive skewness, got %v", got)
			}
			if tc.wantNegSign && !(got < 0) {
				t.Fatalf("expected negative skewness, got %v", got)
			}
		})
	}
}

func TestSampleSkewness_EdgeCases(t *testing.T) {
	cases := []struct {
		name     string
		data     Float64Data
		wantErr  error
		want     float64
		wantZero bool
	}{
		{"too few", Float64Data{1, 2}, ErrEmptyInput, math.NaN(), false},
		{"zero skew", Float64Data{-1, 0, 1}, nil, 0.0, true},
		{"propagate zero variance", Float64Data{5, 5, 5}, ErrZero, math.NaN(), false},
		{"adjusted skew", Float64Data{1, 1, 1, 2, 10}, nil, 0.0, false}, // expected computed later
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleSkewness(tc.data)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantZero {
				if got != 0.0 {
					t.Fatalf("expected zero result, got %v", got)
				}
				return
			}
			if tc.name == "adjusted skew" {
				// compute expected using PopulationSkewness and the adjustment formula
				g1, _ := PopulationSkewness(tc.data)
				n := float64(tc.data.Len())
				expected := g1 * math.Sqrt(n*(n-1)) / (n - 2)
				skewnessApproxEqual(t, got, expected)
				return
			}
			// generic fallback
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestSkewness_Forward(t *testing.T) {
	data := Float64Data{1, 1, 1, 2, 10}
	pop, err1 := PopulationSkewness(data)
	if err1 != nil {
		t.Fatalf("PopulationSkewness error: %v", err1)
	}
	got, err2 := Skewness(data)
	if err2 != nil {
		t.Fatalf("Skewness error: %v", err2)
	}
	skewnessApproxEqual(t, got, pop)
}
