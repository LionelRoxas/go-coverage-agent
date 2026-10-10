package stats

import (
	"errors"
	"math"
	"testing"
)

func meanApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestGeometricMean(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  float64
		err   error
	}{
		{"Empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"Negative", Float64Data{-2, 4}, math.NaN(), NegativeErr},
		{"Zero", Float64Data{0, 5}, math.NaN(), ZeroErr},
		{"Single", Float64Data{7}, 7, nil},
		{"Multiple", Float64Data{1, 4, 9}, math.Exp((math.Log(1) + math.Log(4) + math.Log(9)) / 3), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := GeometricMean(tc.input)
			if !errors.Is(err, tc.err) {
				t.Fatalf("expected error %v, got %v", tc.err, err)
			}
			if tc.err == nil {
				if !meanApproxEqual(got, tc.want) {
					t.Errorf("expected %v, got %v", tc.want, got)
				}
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result, got %v", got)
				}
			}
		})
	}
}

func TestHarmonicMean(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  float64
		err   error
	}{
		{"Empty", Float64Data{}, math.NaN(), EmptyInputErr},
		{"Negative", Float64Data{-3, 6}, math.NaN(), NegativeErr},
		{"Zero", Float64Data{0, 2}, math.NaN(), ZeroErr},
		{"Single", Float64Data{5}, 5, nil},
		{"Multiple", Float64Data{1, 2, 4}, 3.0 / (1 + 0.5 + 0.25), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := HarmonicMean(tc.input)
			if !errors.Is(err, tc.err) {
				t.Fatalf("expected error %v, got %v", tc.err, err)
			}
			if tc.err == nil {
				if !meanApproxEqual(got, tc.want) {
					t.Errorf("expected %v, got %v", tc.want, got)
				}
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result, got %v", got)
				}
			}
		})
	}
}
