package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestHistogram_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		bins    int
		wantErr error
	}{
		{"empty input", Float64Data{}, 3, ErrEmptyInput},
		{"zero bins", Float64Data{1, 2, 3}, 0, ErrBounds},
		{"negative bins", Float64Data{1, 2, 3}, -2, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, _, err := Histogram(tc.input, tc.bins)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestHistogram_EqualValues(t *testing.T) {
	input := Float64Data{5, 5, 5}
	bins := 2
	counts, edges, err := Histogram(input, bins)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedEdges := []float64{4.5, 5.0, 5.5}
	expectedCounts := []int{0, 3}
	if !reflect.DeepEqual(edges, expectedEdges) {
		t.Fatalf("edges mismatch: got %v want %v", edges, expectedEdges)
	}
	if !reflect.DeepEqual(counts, expectedCounts) {
		t.Fatalf("counts mismatch: got %v want %v", counts, expectedCounts)
	}
}

func TestHistogram_Normal(t *testing.T) {
	input := Float64Data{1, 2, 3, 4}
	bins := 3
	counts, edges, err := Histogram(input, bins)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expectedEdges := []float64{1, 2, 3, 4}
	expectedCounts := []int{1, 1, 2}
	if !reflect.DeepEqual(edges, expectedEdges) {
		t.Fatalf("edges mismatch: got %v want %v", edges, expectedEdges)
	}
	if !reflect.DeepEqual(counts, expectedCounts) {
		t.Fatalf("counts mismatch: got %v want %v", counts, expectedCounts)
	}
}

func TestFloat64Data_Histogram(t *testing.T) {
	input := Float64Data{0, 10}
	bins := 1
	counts1, edges1, err1 := Histogram(input, bins)
	counts2, edges2, err2 := input.Histogram(bins)
	if err1 != nil || err2 != nil {
		t.Fatalf("unexpected errors: %v %v", err1, err2)
	}
	if !reflect.DeepEqual(counts1, counts2) || !reflect.DeepEqual(edges1, edges2) {
		t.Fatalf("method and function results differ: %v vs %v, %v vs %v", counts1, counts2, edges1, edges2)
	}
}
