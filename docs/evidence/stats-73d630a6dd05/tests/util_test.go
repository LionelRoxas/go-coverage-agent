package stats

import (
	"math"
	"testing"
)

type utilCase struct {
	name  string
	input float64
	want  int
}

func TestFloat64ToInt_Rounding(t *testing.T) {
	cases := []utilCase{
		{name: "positive below .5", input: 2.3, want: 2},
		{name: "positive above .5", input: 2.7, want: 3},
		{name: "positive half away from zero", input: 2.5, want: 3},
		{name: "negative half away from zero", input: -2.5, want: -3},
		{name: "negative below .5", input: -2.3, want: -2},
		{name: "negative above .5", input: -2.7, want: -3},
		{name: "zero", input: 0.0, want: 0},
		{name: "large integer", input: 123456789.0, want: 123456789},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got := float64ToInt(tc.input)
			if got != tc.want {
				t.Fatalf("float64ToInt(%v) = %d, want %d", tc.input, got, tc.want)
			}
		})
	}
}

func TestFloat64ToInt_NaNInf_NoPanic(t *testing.T) {
	inputs := []float64{math.NaN(), math.Inf(1), math.Inf(-1)}
	for _, v := range inputs {
		// Ensure the function does not panic; ignore the result.
		_ = float64ToInt(v)
	}
}
