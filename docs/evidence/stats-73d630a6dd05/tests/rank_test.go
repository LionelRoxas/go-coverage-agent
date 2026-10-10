package stats

import (
	"math"
	"testing"
)

func rankApproxEqual(got, want []float64) bool {
	if len(got) != len(want) {
		return false
	}
	const eps = 1e-9
	for i := range got {
		if math.Abs(got[i]-want[i]) > eps {
			return false
		}
	}
	return true
}

func TestRank_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := Rank(empty)
	if err == nil {
		t.Fatalf("expected error, got nil")
	}
	if err != ErrEmptyInput {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}

func TestRank_DistinctValues(t *testing.T) {
	data := Float64Data{10, 20, 30}
	got, err := Rank(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{1, 2, 3}
	if !rankApproxEqual(got, want) {
		t.Fatalf("ranks mismatch: got %v, want %v", got, want)
	}
}

func TestRank_Ties(t *testing.T) {
	data := Float64Data{5, 5, 10}
	got, err := Rank(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{1.5, 1.5, 3}
	if !rankApproxEqual(got, want) {
		t.Fatalf("ranks mismatch: got %v, want %v", got, want)
	}
}

func TestFloat64Data_Rank(t *testing.T) {
	data := Float64Data{3, 1, 2}
	got1, err1 := Rank(data)
	if err1 != nil {
		t.Fatalf("Rank error: %v", err1)
	}
	got2, err2 := data.Rank()
	if err2 != nil {
		t.Fatalf("Float64Data.Rank error: %v", err2)
	}
	if !rankApproxEqual(got1, got2) {
		t.Fatalf("method Rank differs from function Rank: %v vs %v", got2, got1)
	}
}
