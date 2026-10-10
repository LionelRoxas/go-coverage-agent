package stats

import (
	"errors"
	"math"
	"testing"
)

func roundApproxEqual(t *testing.T, got, want float64) {
	const tol = 1e-9
	if math.IsNaN(want) {
		if !math.IsNaN(got) {
			t.Errorf("expected NaN, got %v", got)
		}
		return
	}
	if math.Abs(got-want) > tol {
		t.Errorf("expected %v, got %v (diff %v > %v)", want, got, math.Abs(got-want), tol)
	}
}

func TestRound(t *testing.T) {
	cases := []struct {
		name    string
		input   float64
		places  int
		want    float64
		wantErr error
	}{
		{name: "NaN input", input: math.NaN(), places: 2, want: math.NaN(), wantErr: NaNErr},
		{name: "positive rounding", input: 1.2345, places: 2, want: 1.23, wantErr: nil},
		{name: "negative rounding", input: -1.235, places: 2, want: -1.24, wantErr: nil},
		{name: "zero places", input: 1.5, places: 0, want: 2.0, wantErr: nil},
		{name: "negative places", input: 1234.56, places: -2, want: 1200.0, wantErr: nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Round(tc.input, tc.places)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			roundApproxEqual(t, got, tc.want)
		})
	}
}
