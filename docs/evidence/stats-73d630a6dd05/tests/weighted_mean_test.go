package stats

import (
	"errors"
	"math"
	"testing"
)

func TestWeightedMean_EmptyInput(t *testing.T) {
	data := Float64Data{}
	weights := Float64Data{1}
	got, err := WeightedMean(data, weights)
	if !math.IsNaN(got) {
		t.Errorf("expected NaN result for empty input, got %v", got)
	}
	if !errors.Is(err, ErrEmptyInput) {
		t.Errorf("expected ErrEmptyInput, got %v", err)
	}
}

func TestWeightedMean_SizeMismatch(t *testing.T) {
	data := Float64Data{1, 2}
	weights := Float64Data{1}
	got, err := WeightedMean(data, weights)
	if !math.IsNaN(got) {
		t.Errorf("expected NaN result for size mismatch, got %v", got)
	}
	if !errors.Is(err, ErrSize) {
		t.Errorf("expected ErrSize, got %v", err)
	}
}

func TestWeightedMean_NegativeWeight(t *testing.T) {
	data := Float64Data{1, 2}
	weights := Float64Data{1, -1}
	got, err := WeightedMean(data, weights)
	if !math.IsNaN(got) {
		t.Errorf("expected NaN result for negative weight, got %v", got)
	}
	if !errors.Is(err, ErrNegative) {
		t.Errorf("expected ErrNegative, got %v", err)
	}
}

func TestWeightedMean_ZeroWeight(t *testing.T) {
	data := Float64Data{1, 2}
	weights := Float64Data{0, 0}
	got, err := WeightedMean(data, weights)
	if !math.IsNaN(got) {
		t.Errorf("expected NaN result for zero total weight, got %v", got)
	}
	if !errors.Is(err, ErrZero) {
		t.Errorf("expected ErrZero, got %v", err)
	}
}

func TestWeightedMean_Correct(t *testing.T) {
	data := Float64Data{1, 2, 3}
	weights := Float64Data{1, 1, 2}
	got, err := WeightedMean(data, weights)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := 9.0 / 4.0 // 2.25
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("weighted mean = %v, want %v", got, want)
	}
}

func TestFloat64Data_WeightedMean_Method(t *testing.T) {
	data := Float64Data{4, 6}
	weights := Float64Data{0.5, 1.5}
	got, err := data.WeightedMean(weights)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Expected: (4*0.5 + 6*1.5) / (0.5+1.5) = (2 + 9) / 2 = 5.5
	want := 5.5
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("method weighted mean = %v, want %v", got, want)
	}
}
