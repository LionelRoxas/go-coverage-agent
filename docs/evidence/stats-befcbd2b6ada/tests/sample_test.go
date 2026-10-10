package stats

import (
	"errors"
	"testing"
)

func sampleContainsAll(t *testing.T, input []float64, result []float64) {
	for _, v := range result {
		found := false
		for _, iv := range input {
			if v == iv {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("result element %v not found in input", v)
		}
	}
}

func sampleIsSubsequence(t *testing.T, input []float64, result []float64) {
	idx := 0
	for _, v := range result {
		found := false
		for i := idx; i < len(input); i++ {
			if input[i] == v {
				idx = i + 1
				found = true
				break
			}
		}
		if !found {
			t.Errorf("result element %v not in original order of input", v)
			return
		}
	}
}

func TestSample(t *testing.T) {
	cases := []struct {
		name        string
		input       Float64Data
		takenum     int
		replacement bool
		wantErr     error
		wantLen     int
		check       func(t *testing.T, got []float64)
	}{
		{
			name:        "empty input",
			input:       Float64Data{},
			takenum:     1,
			replacement: false,
			wantErr:     EmptyInputErr,
		},
		{
			name:        "replacement true",
			input:       Float64Data{1, 2, 3},
			takenum:     5,
			replacement: true,
			wantErr:     nil,
			wantLen:     5,
			check: func(t *testing.T, got []float64) {
				sampleContainsAll(t, []float64{1, 2, 3}, got)
			},
		},
		{
			name:        "replacement false valid",
			input:       Float64Data{10, 20, 30, 40},
			takenum:     3,
			replacement: false,
			wantErr:     nil,
			wantLen:     3,
			check: func(t *testing.T, got []float64) {
				// ensure no duplicate values
				seen := make(map[float64]bool)
				for _, v := range got {
					if seen[v] {
						t.Errorf("duplicate value %v in result", v)
					}
					seen[v] = true
				}
				sampleContainsAll(t, []float64{10, 20, 30, 40}, got)
			},
		},
		{
			name:        "bounds error",
			input:       Float64Data{1, 2},
			takenum:     5,
			replacement: false,
			wantErr:     BoundsErr,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Sample(tc.input, tc.takenum, tc.replacement)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != tc.wantLen {
				t.Fatalf("expected length %d, got %d", tc.wantLen, len(got))
			}
			if tc.check != nil {
				tc.check(t, got)
			}
		})
	}
}

func TestStableSample(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		takenum int
		wantErr error
		wantLen int
		check   func(t *testing.T, got []float64)
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			takenum: 1,
			wantErr: EmptyInputErr,
		},
		{
			name:    "valid subsequence",
			input:   Float64Data{5, 10, 15, 20, 25},
			takenum: 3,
			wantErr: nil,
			wantLen: 3,
			check: func(t *testing.T, got []float64) {
				sampleIsSubsequence(t, []float64{5, 10, 15, 20, 25}, got)
				sampleContainsAll(t, []float64{5, 10, 15, 20, 25}, got)
			},
		},
		{
			name:    "bounds error",
			input:   Float64Data{1, 2, 3},
			takenum: 5,
			wantErr: BoundsErr,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := StableSample(tc.input, tc.takenum)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != tc.wantLen {
				t.Fatalf("expected length %d, got %d", tc.wantLen, len(got))
			}
			if tc.check != nil {
				tc.check(t, got)
			}
		})
	}
}
