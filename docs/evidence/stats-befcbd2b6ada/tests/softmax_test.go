package stats

import (
	"errors"
	"math"
	"testing"
)

var softmaxTestCases = []struct {
	name  string
	input Float64Data
}{
	{"simple", Float64Data{1, 2, 3}},
	{"large values", Float64Data{1000, 1001, 1002}},
	{"negative values", Float64Data{-1, -2, -3}},
}

func TestSoftMax_EmptyInput(t *testing.T) {
	var empty Float64Data
	got, err := SoftMax(empty)
	if !errors.Is(err, EmptyInput) {
		t.Fatalf("expected EmptyInput error, got %v", err)
	}
	if got != nil && len(got) != 0 {
		t.Fatalf("expected empty slice on error, got %v", got)
	}
}

func TestSoftMax_Basic(t *testing.T) {
	for _, tc := range softmaxTestCases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SoftMax(tc.input)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.input) {
				t.Fatalf("length mismatch: got %d want %d", len(got), len(tc.input))
			}
			// compute stable expected values
			maxVal := tc.input[0]
			for _, v := range tc.input {
				if v > maxVal {
					maxVal = v
				}
			}
			sumExp := 0.0
			for _, v := range tc.input {
				sumExp += math.Exp(v - maxVal)
			}
			sumProb := 0.0
			for i, v := range tc.input {
				expected := math.Exp(v-maxVal) / sumExp
				if math.Abs(got[i]-expected) > 1e-9 {
					t.Errorf("value %d mismatch: got %v want %v", i, got[i], expected)
				}
				if got[i] < 0 || got[i] > 1 {
					t.Errorf("probability out of range [0,1]: %v", got[i])
				}
				sumProb += got[i]
			}
			if math.Abs(sumProb-1) > 1e-9 {
				t.Errorf("sum of probabilities %v not close to 1", sumProb)
			}
		})
	}
}
