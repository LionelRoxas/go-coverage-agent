package stats

import (
	"errors"
	"math"
	"testing"
)

func roundApproxEqual(got, want float64) bool {
	if math.IsNaN(want) {
		return math.IsNaN(got)
	}
	return math.Abs(got-want) <= 1e-9
}

func TestRound_Coverage(t *testing.T) {
	cases := []struct {
		name    string
		input   float64
		places  int
		want    float64
		wantErr error
	}{
		{name: "NaN input", input: math.NaN(), places: 2, want: math.NaN(), wantErr: NaNErr},
		{name: "Positive rounding", input: 1.2345, places: 2, want: 1.23, wantErr: nil},
		{name: "Zero places", input: 2.5, places: 0, want: 3.0, wantErr: nil},
		{name: "Negative places", input: 1234.5, places: -2, want: 1200.0, wantErr: nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Round(tc.input, tc.places)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !roundApproxEqual(got, tc.want) {
				t.Fatalf("rounded result = %v, want %v", got, tc.want)
			}
		})
	}
}
