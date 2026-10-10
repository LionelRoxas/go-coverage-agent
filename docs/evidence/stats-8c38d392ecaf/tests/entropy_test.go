package stats

import (
	"errors"
	"math"
	"testing"
)

func entropyApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestNormalize_Success(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  []float64
	}{
		{"simple", Float64Data{1, 2, 3}, []float64{1.0 / 6, 2.0 / 6, 3.0 / 6}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := normalize(tc.input)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("length mismatch: got %d want %d", len(got), len(tc.want))
			}
			for i := range got {
				if !entropyApproxEqual(got[i], tc.want[i]) {
					t.Errorf("index %d: got %v want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestNormalize_EmptyInput(t *testing.T) {
	_, err := normalize(Float64Data{})
	if err == nil {
		t.Fatalf("expected error for empty input")
	}
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestEntropy_Normal(t *testing.T) {
	input := Float64Data{0, 1, 2, 3}
	got, err := Entropy(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// compute expected entropy manually
	sum := 0.0
	for _, v := range input {
		sum += v
	}
	var exp float64
	for _, v := range input {
		if v == 0 {
			continue
		}
		nv := v / sum
		exp -= nv * math.Log(nv)
	}
	if !entropyApproxEqual(got, exp) {
		t.Errorf("entropy = %v, want %v", got, exp)
	}
}

func TestEntropy_EmptyInput(t *testing.T) {
	_, err := Entropy(Float64Data{})
	if err == nil {
		t.Fatalf("expected error for empty input")
	}
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestEntropy_AllZeros(t *testing.T) {
	input := Float64Data{0, 0, 0}
	got, err := Entropy(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !math.IsNaN(got) {
		t.Errorf("expected NaN result, got %v", got)
	}
}
