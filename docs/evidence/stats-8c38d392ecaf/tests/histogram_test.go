package stats

import (
	"errors"
	"math"
	"testing"
)

func histogramFloatSlicesEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-9
	for i := range a {
		if math.IsNaN(a[i]) && math.IsNaN(b[i]) {
			continue
		}
		if math.Abs(a[i]-b[i]) > eps {
			return false
		}
	}
	return true
}

func TestHistogram_EmptyInput(t *testing.T) {
	_, _, err := Histogram(Float64Data{}, 5)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestHistogram_BinsBounds(t *testing.T) {
	input := Float64Data{1, 2, 3}
	_, _, err := Histogram(input, 0)
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds, got %v", err)
	}
}

func TestHistogram_AllEqual(t *testing.T) {
	input := Float64Data{2, 2, 2}
	counts, edges, err := Histogram(input, 2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedCounts := []int{0, 3}
	if len(counts) != len(expectedCounts) {
		t.Fatalf("counts length mismatch: got %d want %d", len(counts), len(expectedCounts))
	}
	for i, v := range expectedCounts {
		if counts[i] != v {
			t.Fatalf("counts mismatch at %d: got %d want %d", i, counts[i], v)
		}
	}
	expectedEdges := []float64{1.5, 2.0, 2.5}
	if !histogramFloatSlicesEqual(edges, expectedEdges) {
		t.Fatalf("edges mismatch: got %v want %v", edges, expectedEdges)
	}
}

func TestHistogram_Normal(t *testing.T) {
	input := Float64Data{0, 1, 2, 3, 4}
	bins := 4
	counts, edges, err := Histogram(input, bins)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(edges) != bins+1 {
		t.Fatalf("edges length %d, want %d", len(edges), bins+1)
	}
	expectedCounts := []int{1, 1, 1, 2}
	if len(counts) != len(expectedCounts) {
		t.Fatalf("counts length mismatch: got %d want %d", len(counts), len(expectedCounts))
	}
	for i, v := range expectedCounts {
		if counts[i] != v {
			t.Fatalf("counts mismatch at %d: got %d want %d", i, counts[i], v)
		}
	}
	sum := 0
	for _, c := range counts {
		sum += c
	}
	if sum != len(input) {
		t.Fatalf("sum of counts %d, want %d", sum, len(input))
	}
}

func TestFloat64Data_Histogram_Method(t *testing.T) {
	input := Float64Data{5, 5, 5}
	counts, edges, err := input.Histogram(3)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(edges) != 4 {
		t.Fatalf("edges length %d, want 4", len(edges))
	}
	sum := 0
	for _, c := range counts {
		sum += c
	}
	if sum != len(input) {
		t.Fatalf("sum of counts %d, want %d", sum, len(input))
	}
}
