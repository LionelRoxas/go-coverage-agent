package stats

import (
	"errors"
	"testing"
)

func sampleAllInInput(input []float64, result []float64) bool {
	m := make(map[float64]int)
	for _, v := range input {
		m[v]++
	}
	for _, v := range result {
		if cnt, ok := m[v]; !ok || cnt == 0 {
			return false
		}
		m[v]--
	}
	return true
}

func sampleIsSubsequence(input []float64, result []float64) bool {
	if len(result) == 0 {
		return true
	}
	idx := 0
	for _, v := range input {
		if v == result[idx] {
			idx++
			if idx == len(result) {
				return true
			}
		}
	}
	return false
}

func TestStableSample(t *testing.T) {
	cases := []struct {
		name      string
		input     Float64Data
		takenum   int
		wantErr   error
		checkFunc func([]float64) bool
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			takenum: 1,
			wantErr: EmptyInputErr,
		},
		{
			name:    "valid stable sample",
			input:   Float64Data{5, 1, 3, 2},
			takenum: 2,
			wantErr: nil,
			checkFunc: func(res []float64) bool {
				if len(res) != 2 {
					return false
				}
				// result must be a subsequence preserving order
				return sampleIsSubsequence([]float64{5, 1, 3, 2}, res) && sampleAllInInput([]float64{5, 1, 3, 2}, res)
			},
		},
		{
			name:    "bounds error",
			input:   Float64Data{7, 8},
			takenum: 5,
			wantErr: BoundsErr,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := StableSample(tc.input, tc.takenum)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.checkFunc != nil && !tc.checkFunc(got) {
				t.Fatalf("result failed property check: %v", got)
			}
		})
	}
}

func TestSample_EmptyInput(t *testing.T) {
	input := Float64Data{}
	_, err := Sample(input, 3, true)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestSample_WithReplacement(t *testing.T) {
	input := Float64Data{1.0, 2.0, 3.0}
	taken := 5
	result, err := Sample(input, taken, true)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != taken {
		t.Fatalf("expected %d samples, got %d", taken, len(result))
	}
	for _, v := range result {
		if v != 1.0 && v != 2.0 && v != 3.0 {
			t.Fatalf("sampled value %v not in original input", v)
		}
	}
}

func TestSample_WithoutReplacement(t *testing.T) {
	input := Float64Data{10.0, 20.0, 30.0, 40.0}
	taken := 3
	result, err := Sample(input, taken, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != taken {
		t.Fatalf("expected %d samples, got %d", taken, len(result))
	}
	seen := make(map[float64]bool)
	for _, v := range result {
		// ensure value exists in input
		found := false
		for _, iv := range input {
			if iv == v {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("sampled value %v not present in input", v)
		}
		if seen[v] {
			t.Fatalf("duplicate value %v found in without‑replacement sample", v)
		}
		seen[v] = true
	}
}

func TestSample_BoundsError(t *testing.T) {
	input := Float64Data{1.0, 2.0}
	taken := 5
	result, err := Sample(input, taken, false)
	if !errors.Is(err, BoundsErr) {
		t.Fatalf("expected BoundsErr, got %v", err)
	}
	if result != nil {
		t.Fatalf("expected nil result on error, got %v", result)
	}
}
