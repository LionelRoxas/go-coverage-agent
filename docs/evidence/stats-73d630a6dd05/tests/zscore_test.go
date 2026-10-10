package stats

import (
	"errors"
	"math"
	"testing"
)

func zscoreApproxEqual(got, want []float64) bool {
	if len(got) != len(want) {
		return false
	}
	const eps = 1e-9
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > eps {
			return false
		}
	}
	return true
}

func TestZScore_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := ZScore(empty)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestZScore_ZeroStdDev(t *testing.T) {
	data := Float64Data{5, 5, 5}
	_, err := ZScore(data)
	if !errors.Is(err, ErrZero) {
		t.Fatalf("expected ErrZero, got %v", err)
	}
}

func TestZScore_Normal(t *testing.T) {
	data := Float64Data{1, 2, 3}
	got, err := ZScore(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{-1, 0, 1}
	if !zscoreApproxEqual(got, want) {
		t.Fatalf("ZScore mismatch: got %v, want %v", got, want)
	}
}

func TestFloat64Data_ZScore_Method(t *testing.T) {
	data := Float64Data{10, 20, 30}
	got, err := data.ZScore()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	m, _ := Mean(data)
	sd, _ := StandardDeviationSample(data)
	expected := make([]float64, len(data))
	for i, v := range data {
		expected[i] = (v - m) / sd
	}
	if !zscoreApproxEqual(got, expected) {
		t.Fatalf("method ZScore mismatch: got %v, want %v", got, expected)
	}
}
