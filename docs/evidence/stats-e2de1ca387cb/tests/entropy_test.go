package stats

import (
	"errors"
	"math"
	"testing"
)

func TestNormalize_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name     string
		input    Float64Data
		wantErr  bool
		wantVals []float64
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			wantErr: true,
		},
		{
			name:     "normal values",
			input:    Float64Data{1, 2, 3},
			wantErr:  false,
			wantVals: []float64{1.0 / 6.0, 2.0 / 6.0, 3.0 / 6.0},
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := normalize(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, EmptyInputErr) {
					t.Fatalf("expected EmptyInputErr, got %v", err)
				}
				if len(got) != 0 {
					t.Fatalf("expected empty result on error, got length %d", len(got))
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.wantVals) {
				t.Fatalf("result length mismatch: got %d, want %d", len(got), len(tc.wantVals))
			}
			// ensure original input unchanged
			for i, v := range tc.input {
				if v != []float64{1, 2, 3}[i] {
					t.Fatalf("original input modified at index %d", i)
				}
			}
			for i, want := range tc.wantVals {
				if math.Abs(got[i]-want) > 1e-9 {
					t.Fatalf("value mismatch at %d: got %v, want %v", i, got[i], want)
				}
			}
		})
	}
}

func TestEntropy_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		wantErr bool
		want    float64
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			wantErr: true,
		},
		{
			name:    "zero and positive values",
			input:   Float64Data{0, 1, 1},
			wantErr: false,
			want:    math.Log(2),
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Entropy(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, EmptyInputErr) {
					t.Fatalf("expected EmptyInputErr, got %v", err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("entropy mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}
