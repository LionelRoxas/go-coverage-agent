package stats

import (
	"math"
	"testing"
)

func entropyApproxEqual(t *testing.T, got, want float64) {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > eps {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestNormalize_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := normalize(empty)
	if err == nil {
		t.Fatalf("expected error for empty input")
	}
}

func TestNormalize_Basic(t *testing.T) {
	input := Float64Data{1, 2, 3}
	normalized, err := normalize(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := []float64{1.0 / 6, 2.0 / 6, 3.0 / 6}
	for i, v := range normalized {
		if math.Abs(v-expected[i]) > 1e-9 {
			t.Fatalf("index %d: got %v, want %v", i, v, expected[i])
		}
	}
	if input[0] != 1 || input[1] != 2 || input[2] != 3 {
		t.Fatalf("original input modified")
	}
}

func TestEntropy_Basic(t *testing.T) {
	input := Float64Data{0.5, 0.5}
	got, err := Entropy(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := -(0.5*math.Log(0.5) + 0.5*math.Log(0.5))
	entropyApproxEqual(t, got, want)
}

func TestEntropy_WithZero(t *testing.T) {
	input := Float64Data{0, 1}
	got, err := Entropy(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(got) > 1e-9 {
		t.Fatalf("expected entropy 0, got %v", got)
	}
}

func TestEntropy_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := Entropy(empty)
	if err == nil {
		t.Fatalf("expected error for empty input")
	}
}
