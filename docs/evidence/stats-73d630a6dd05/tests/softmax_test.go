package stats

import (
	"errors"
	"math"
	"testing"
)

func TestSoftMax_EmptyInput(t *testing.T) {
	var input Float64Data
	got, err := SoftMax(input)
	if !errors.Is(err, EmptyInput) {
		t.Fatalf("expected EmptyInput error, got %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("expected empty slice on error, got length %d", len(got))
	}
}

func TestSoftMax_Basic(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
	}{
		{"positive", Float64Data{1, 2, 3}},
		{"negative", Float64Data{-1, -2, -3}},
		{"mixed", Float64Data{0, -1, 1}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SoftMax(tc.input)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.input) {
				t.Fatalf("output length %d does not match input length %d", len(got), len(tc.input))
			}
			for i, v := range got {
				if v < 0 || v > 1 {
					t.Fatalf("probability at index %d out of range: %v", i, v)
				}
			}
			sum := 0.0
			for _, v := range got {
				sum += v
			}
			if math.Abs(sum-1) > 1e-9 {
				t.Fatalf("sum of probabilities %v not close to 1", sum)
			}
			// verify max index correspondence
			maxIdx := 0
			maxVal := tc.input[0]
			for i, v := range tc.input {
				if v > maxVal {
					maxVal = v
					maxIdx = i
				}
			}
			maxOutIdx := 0
			maxOutVal := got[0]
			for i, v := range got {
				if v > maxOutVal {
					maxOutVal = v
					maxOutIdx = i
				}
			}
			if maxIdx != maxOutIdx {
				t.Fatalf("max input index %d does not match max output index %d", maxIdx, maxOutIdx)
			}
		})
	}
}
