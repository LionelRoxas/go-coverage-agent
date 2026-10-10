package stats

import (
	"errors"
	"math"
	"reflect"
	"testing"
)

func histogramFloatSlicesEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-9
	for i := range a {
		if math.Abs(a[i]-b[i]) > eps {
			return false
		}
	}
	return true
}

func TestHistogram_EmptyInput(t *testing.T) {
	var input Float64Data
	counts, edges, err := Histogram(input, 3)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
	if counts != nil || edges != nil {
		t.Fatalf("expected nil slices on error, got counts=%v edges=%v", counts, edges)
	}
}

func TestHistogram_InvalidBins(t *testing.T) {
	input := Float64Data{1, 2, 3}
	_, _, err := Histogram(input, 0)
	if !errors.Is(err, ErrBounds) {
		t.Fatalf("expected ErrBounds, got %v", err)
	}
}

func TestHistogram_AllEqualValues(t *testing.T) {
	input := Float64Data{2.0, 2.0, 2.0}
	counts, edges, err := Histogram(input, 2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedEdges := []float64{1.5, 2.0, 2.5}
	if !histogramFloatSlicesEqual(edges, expectedEdges) {
		t.Fatalf("edges mismatch: got %v want %v", edges, expectedEdges)
	}
	expectedCounts := []int{0, 3}
	if !reflect.DeepEqual(counts, expectedCounts) {
		t.Fatalf("counts mismatch: got %v want %v", counts, expectedCounts)
	}
}

func TestHistogram_NormalCase(t *testing.T) {
	input := Float64Data{0.0, 0.5, 1.0, 1.5, 2.0}
	counts, edges, err := Histogram(input, 2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedEdges := []float64{0.0, 1.0, 2.0}
	if !histogramFloatSlicesEqual(edges, expectedEdges) {
		t.Fatalf("edges mismatch: got %v want %v", edges, expectedEdges)
	}
	expectedCounts := []int{2, 3}
	if !reflect.DeepEqual(counts, expectedCounts) {
		t.Fatalf("counts mismatch: got %v want %v", counts, expectedCounts)
	}
}

func TestFloat64Data_Histogram_Forward(t *testing.T) {
	input := Float64Data{0.0, 0.5, 1.0, 1.5, 2.0}
	counts1, edges1, err1 := Histogram(input, 2)
	counts2, edges2, err2 := input.Histogram(2)
	if err1 != nil || err2 != nil {
		t.Fatalf("unexpected errors: %v %v", err1, err2)
	}
	if !reflect.DeepEqual(counts1, counts2) || !histogramFloatSlicesEqual(edges1, edges2) {
		t.Fatalf("method forward mismatch: got %v,%v vs %v,%v", counts1, edges1, counts2, edges2)
	}
}
