package stats

import (
	"errors"
	"math"
	"testing"
)

func ewmaSlicesEqual(got, want []float64, tol float64) bool {
	if len(got) != len(want) {
		return false
	}
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > tol {
			return false
		}
	}
	return true
}

func TestEWMA_EmptyInput(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		alpha float64
	}{{
		name:  "empty slice",
		input: Float64Data{},
		alpha: 0.5,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := EWMA(tc.input, tc.alpha)
			if !errors.Is(err, ErrEmptyInput) {
				t.Fatalf("expected ErrEmptyInput, got %v", err)
			}
		})
	}
}

func TestEWMA_Bounds(t *testing.T) {
	input := Float64Data{1, 2, 3}
	cases := []struct {
		name  string
		alpha float64
	}{{
		name:  "alpha zero",
		alpha: 0.0,
	}, {
		name:  "alpha negative",
		alpha: -0.1,
	}, {
		name:  "alpha greater than one",
		alpha: 1.1,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := EWMA(input, tc.alpha)
			if !errors.Is(err, ErrBounds) {
				t.Fatalf("expected ErrBounds for alpha %v, got %v", tc.alpha, err)
			}
		})
	}
}

func TestEWMA_Calculation(t *testing.T) {
	const tol = 1e-9
	cases := []struct {
		name   string
		input  Float64Data
		alpha  float64
		expect []float64
	}{{
		name:   "alpha 0.5 simple",
		input:  Float64Data{1, 2, 3},
		alpha:  0.5,
		expect: []float64{1, 1.5, 2.25},
	}, {
		name:   "alpha 1 copies input",
		input:  Float64Data{5, 10, 15},
		alpha:  1.0,
		expect: []float64{5, 10, 15},
	}, {
		name:   "alpha 0.2 longer slice",
		input:  Float64Data{10, 20, 30, 40},
		alpha:  0.2,
		expect: []float64{10, 12, 15.6, 20.48},
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := EWMA(tc.input, tc.alpha)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !ewmaSlicesEqual(got, tc.expect, tol) {
				t.Fatalf("EWMA result mismatch. got %v, want %v", got, tc.expect)
			}
		})
	}
}

func TestFloat64Data_EWMA_Forward(t *testing.T) {
	const tol = 1e-9
	input := Float64Data{2, 4, 6, 8}
	alpha := 0.3
	gotFunc, err1 := EWMA(input, alpha)
	if err1 != nil {
		t.Fatalf("EWMA function returned error: %v", err1)
	}
	gotMethod, err2 := input.EWMA(alpha)
	if err2 != nil {
		t.Fatalf("Float64Data.EWMA returned error: %v", err2)
	}
	if !ewmaSlicesEqual(gotFunc, gotMethod, tol) {
		t.Fatalf("method result differs from function. func %v, method %v", gotFunc, gotMethod)
	}
}
