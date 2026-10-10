package stats

import (
	"errors"
	"math"
	"testing"
)

func TestMode(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, EmptyInputErr},
		{"single", Float64Data{5}, []float64{5}, nil},
		{"distinct", Float64Data{1, 2, 3}, []float64{}, nil},
		{"single mode", Float64Data{2, 2, 1, 3}, []float64{2}, nil},
		{"multiple modes", Float64Data{1, 1, 2, 2, 3}, []float64{1, 2}, nil},
		{"all same", Float64Data{4, 4, 4}, []float64{4}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Mode(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err != nil {
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d elements, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if math.IsNaN(tc.want[i]) && math.IsNaN(got[i]) {
					continue
				}
				if math.Abs(got[i]-tc.want[i]) > 1e-9 {
					t.Fatalf("at index %d, expected %v, got %v", i, tc.want[i], got[i])
				}
			}
		})
	}
}
