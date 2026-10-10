package stats

import (
	"errors"
	"testing"
)

func sampleAllInInput(t *testing.T, result []float64, input Float64Data) {
	inputSet := make(map[float64]struct{}, len(input))
	for _, v := range input {
		inputSet[v] = struct{}{}
	}
	for _, v := range result {
		if _, ok := inputSet[v]; !ok {
			t.Errorf("value %v not present in original input", v)
		}
	}
}

func sampleNoDuplicates(t *testing.T, result []float64) {
	seen := make(map[float64]struct{}, len(result))
	for _, v := range result {
		if _, ok := seen[v]; ok {
			t.Errorf("duplicate value %v found in result", v)
		}
		seen[v] = struct{}{}
	}
}

func sampleIsSubsequence(t *testing.T, result []float64, input Float64Data) {
	if len(result) == 0 {
		return
	}
	idx := 0
	for _, v := range input {
		if v == result[idx] {
			idx++
			if idx == len(result) {
				return
			}
		}
	}
	t.Errorf("result %v is not a subsequence preserving order of input %v", result, input)
}

func TestSample_Errors(t *testing.T) {
	empty := Float64Data{}
	_, err := Sample(empty, 1, true)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
	_, err = Sample(empty, 1, false)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr for non‑replacement, got %v", err)
	}
}

func TestSample_WithReplacement(t *testing.T) {
	input := Float64Data{1, 2, 3, 4, 5}
	taken := 3
	res, err := Sample(input, taken, true)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != taken {
		t.Fatalf("expected %d elements, got %d", taken, len(res))
	}
	sampleAllInInput(t, res, input)
}

func TestSample_WithoutReplacement(t *testing.T) {
	input := Float64Data{10, 20, 30, 40, 50}
	taken := 4
	res, err := Sample(input, taken, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != taken {
		t.Fatalf("expected %d elements, got %d", taken, len(res))
	}
	sampleAllInInput(t, res, input)
	sampleNoDuplicates(t, res)
}

func TestSample_Bounds(t *testing.T) {
	input := Float64Data{1, 2, 3}
	_, err := Sample(input, 5, false)
	if !errors.Is(err, BoundsErr) {
		t.Fatalf("expected BoundsErr, got %v", err)
	}
}

func TestStableSample_Errors(t *testing.T) {
	empty := Float64Data{}
	_, err := StableSample(empty, 1)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestStableSample_Order(t *testing.T) {
	input := Float64Data{5, 4, 3, 2, 1}
	taken := 3
	res, err := StableSample(input, taken)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res) != taken {
		t.Fatalf("expected %d elements, got %d", taken, len(res))
	}
	// result must be a subsequence preserving original order
	sampleIsSubsequence(t, res, input)
	// also each element must belong to input
	sampleAllInInput(t, res, input)
}

func TestStableSample_Bounds(t *testing.T) {
	input := Float64Data{1, 2, 3}
	_, err := StableSample(input, 4)
	if !errors.Is(err, BoundsErr) {
		t.Fatalf("expected BoundsErr, got %v", err)
	}
}
