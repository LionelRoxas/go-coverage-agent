package stats

import (
	"errors"
	"math"
	"testing"
)

func sigmoidApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestSigmoid_EmptyInput(t *testing.T) {
	var input Float64Data
	got, err := Sigmoid(input)
	if !errors.Is(err, EmptyInput) {
		t.Fatalf("expected EmptyInput error, got %v", err)
	}
	if got != nil && len(got) != 0 {
		t.Fatalf("expected nil or empty result, got %v", got)
	}
}

func TestSigmoid_Basic(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  []float64
	}{
		{"mixed", Float64Data{-1, 0, 1}, []float64{1 / (1 + math.Exp(1)), 0.5, 1 / (1 + math.Exp(-1))}},
		{"largePositive", Float64Data{10}, []float64{1 / (1 + math.Exp(-10))}},
		{"largeNegative", Float64Data{-10}, []float64{1 / (1 + math.Exp(10))}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Sigmoid(tc.input)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				if !sigmoidApproxEqual(got[i], tc.want[i]) {
					t.Fatalf("at index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}
