package stats

import (
	"errors"
	"math"
	"testing"
)

func cumulativeSumSlicesEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-9
	for i := range a {
		if math.Abs(a[i]-b[i]) > eps {
			return false
		}
	}
	return true
}

func TestCumulativeSum(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{
			name:    "empty input returns EmptyInput error",
			input:   Float64Data{},
			want:    []float64{},
			wantErr: EmptyInput,
		},
		{
			name:    "single element returns same value",
			input:   Float64Data{5.0},
			want:    []float64{5.0},
			wantErr: nil,
		},
		{
			name:    "multiple elements with negatives",
			input:   Float64Data{1.0, -2.0, 3.5},
			want:    []float64{1.0, -1.0, 2.5},
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := CumulativeSum(tc.input)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if len(got) != 0 {
					t.Fatalf("expected empty result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !cumulativeSumSlicesEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}
