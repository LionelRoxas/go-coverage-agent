package stats

import (
	"errors"
	"testing"
)

func TestSample_EmptyInput(t *testing.T) {
	var input Float64Data
	_, err := Sample(input, 1, true)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestSample_Replacement(t *testing.T) {
	input := Float64Data{1, 2, 3}
	taken := 5
	result, err := Sample(input, taken, true)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != taken {
		t.Fatalf("expected %d elements, got %d", taken, len(result))
	}
	// all elements must be from input
	allowed := map[float64]bool{1: true, 2: true, 3: true}
	for _, v := range result {
		if !allowed[v] {
			t.Fatalf("value %v not present in input", v)
		}
	}
	// with replacement duplicates are possible; ensure at least one duplicate when taken > len(input)
	dupFound := false
	seen := map[float64]bool{}
	for _, v := range result {
		if seen[v] {
			dupFound = true
			break
		}
		seen[v] = true
	}
	if !dupFound {
		t.Fatalf("expected at least one duplicate value in replacement sampling")
	}
}

func TestSample_NoReplacement(t *testing.T) {
	input := Float64Data{10, 20, 30, 40, 50}
	taken := 3
	result, err := Sample(input, taken, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != taken {
		t.Fatalf("expected %d elements, got %d", taken, len(result))
	}
	// ensure all elements are from input and no duplicates
	allowed := map[float64]bool{10: true, 20: true, 30: true, 40: true, 50: true}
	seen := map[float64]bool{}
	for _, v := range result {
		if !allowed[v] {
			t.Fatalf("value %v not present in input", v)
		}
		if seen[v] {
			t.Fatalf("duplicate value %v found in no‑replacement sampling", v)
		}
		seen[v] = true
	}
}

func TestSample_BoundsError(t *testing.T) {
	input := Float64Data{1, 2, 3}
	_, err := Sample(input, 5, false)
	if !errors.Is(err, BoundsErr) {
		t.Fatalf("expected BoundsErr, got %v", err)
	}
}

func TestStableSample_EmptyInput(t *testing.T) {
	var input Float64Data
	_, err := StableSample(input, 1)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestStableSample_OrderPreserved(t *testing.T) {
	input := Float64Data{5, 10, 15, 20, 25, 30}
	taken := 4
	result, err := StableSample(input, taken)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != taken {
		t.Fatalf("expected %d elements, got %d", taken, len(result))
	}
	// result must be a subsequence of input preserving order
	idx := 0
	for _, v := range result {
		for idx < len(input) && input[idx] != v {
			idx++
		}
		if idx == len(input) {
			t.Fatalf("result element %v not found in input preserving order", v)
		}
		idx++ // move past found element
	}
}

func TestStableSample_BoundsError(t *testing.T) {
	input := Float64Data{1, 2, 3}
	_, err := StableSample(input, 5)
	if !errors.Is(err, BoundsErr) {
		t.Fatalf("expected BoundsErr, got %v", err)
	}
}
