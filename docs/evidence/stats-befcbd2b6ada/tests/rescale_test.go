package stats

import (
	"errors"
	"math"
	"testing"
)

func TestRescale_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := Rescale(empty)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestRescale_ZeroRange(t *testing.T) {
	data := Float64Data{5, 5, 5}
	_, err := Rescale(data)
	if !errors.Is(err, ErrZero) {
		t.Fatalf("expected ErrZero, got %v", err)
	}
}

func TestRescale_Normal(t *testing.T) {
	data := Float64Data{2, 4, 6}
	got, err := Rescale(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{0, 0.5, 1}
	rescaleSlicesClose(t, got, want)
}

func TestFloat64Data_Rescale(t *testing.T) {
	data := Float64Data{-1, 0, 1}
	got, err := data.Rescale()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	exp, err2 := Rescale(data)
	if err2 != nil {
		t.Fatalf("unexpected error from Rescale: %v", err2)
	}
	rescaleSlicesClose(t, got, exp)
}

func rescaleSlicesClose(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	const eps = 1e-9
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > eps {
			t.Fatalf("at index %d: got %v, want %v", i, got[i], want[i])
		}
	}
}
