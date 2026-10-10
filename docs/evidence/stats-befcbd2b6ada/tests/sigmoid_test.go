package stats

import (
	"errors"
	"math"
	"testing"
)

func sigmoidApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestSigmoid_EmptyInput(t *testing.T) {
	got, err := Sigmoid(Float64Data{})
	if !errors.Is(err, EmptyInput) {
		t.Fatalf("expected EmptyInput error, got %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("expected empty result slice, got length %d", len(got))
	}
}

func TestSigmoid_Basic(t *testing.T) {
	cases := []struct {
		name  string
		input []float64
		want  []float64
	}{
		{"zero", []float64{0}, []float64{0.5}},
		{"positive", []float64{2}, []float64{1 / (1 + math.Exp(-2))}},
		{"negative", []float64{-2}, []float64{1 / (1 + math.Exp(2))}},
		{"mixed", []float64{-1, 0, 1}, []float64{1 / (1 + math.Exp(1)), 0.5, 1 / (1 + math.Exp(-1))}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Sigmoid(Float64Data(tc.input))
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("expected length %d, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if !sigmoidApproxEqual(got[i], tc.want[i]) {
					t.Errorf("at index %d: got %v, want %v", i, got[i], tc.want[i])
				}
				if got[i] < 0 || got[i] > 1 {
					t.Errorf("value %v out of expected [0,1] range", got[i])
				}
			}
		})
	}
}
