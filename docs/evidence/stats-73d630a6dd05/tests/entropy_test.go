package stats

import (
	"math"
	"testing"
)

func entropySlicesApproxEqual(a, b Float64Data) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if math.Abs(a[i]-b[i]) > 1e-9 {
			return false
		}
	}
	return true
}

func TestEntropy_Normal(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  float64
	}{
		{
			name:  "simple three values",
			input: Float64Data{1, 2, 3},
			want:  -((1.0/6.0)*math.Log(1.0/6.0) + (2.0/6.0)*math.Log(2.0/6.0) + (3.0/6.0)*math.Log(3.0/6.0)),
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Entropy(tc.input)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("entropy mismatch: got %v want %v", got, tc.want)
			}
		})
	}
}

func TestEntropy_ZeroValues(t *testing.T) {
	input := Float64Data{0, 1, 0, 2}
	// Expected entropy should be computed only on the non‑zero values (1 and 2)
	sum := 3.0
	p1 := 1.0 / sum
	p2 := 2.0 / sum
	want := -(p1*math.Log(p1) + p2*math.Log(p2))
	got, err := Entropy(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("entropy with zeros mismatch: got %v want %v", got, want)
	}
}

func TestEntropy_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := Entropy(empty)
	if err == nil {
		t.Fatalf("expected error for empty input, got nil")
	}
}

func TestNormalize_Basic(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
		want  Float64Data
	}{
		{
			name:  "two equal values",
			input: Float64Data{2, 2},
			want:  Float64Data{0.5, 0.5},
		},
		{
			name:  "mixed values",
			input: Float64Data{1, 3, 6},
			want:  Float64Data{1.0 / 10.0, 3.0 / 10.0, 6.0 / 10.0},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := normalize(tc.input)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !entropySlicesApproxEqual(got, tc.want) {
				t.Fatalf("normalize result mismatch: got %v want %v", got, tc.want)
			}
		})
	}
}

func TestNormalize_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := normalize(empty)
	if err == nil {
		t.Fatalf("expected error for empty input, got nil")
	}
}
