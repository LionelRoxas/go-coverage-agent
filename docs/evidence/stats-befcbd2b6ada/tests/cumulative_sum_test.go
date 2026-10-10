package stats

import (
	"errors"
	"math"
	"testing"
)

func TestCumulativeSum(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, EmptyInput},
		{"single", Float64Data{5}, []float64{5}, nil},
		{"multiple", Float64Data{1, 2, 3, 4}, []float64{1, 3, 6, 10}, nil},
		{"negative", Float64Data{-1, 2, -3}, []float64{-1, 1, -2}, nil},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeSum(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.want) {
					t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
				}
				for i := range got {
					if math.Abs(got[i]-tc.want[i]) > 1e-9 {
						t.Fatalf("at index %d: got %v, want %v", i, got[i], tc.want[i])
					}
				}
			}
		})
	}
}
