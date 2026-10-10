package stats

import (
	"testing"
)

func TestFloat64ToInt_Rounding(t *testing.T) {
	cases := []struct {
		name  string
		input float64
		want  int
	}{
		{"positive less .5", 1.2, 1},
		{"positive .5 up", 1.5, 2},
		{"positive .9 up", 1.9, 2},
		{"negative less .5", -1.2, -1},
		{"negative .5 down", -1.5, -2},
		{"negative .9 down", -1.9, -2},
		{"zero", 0.0, 0},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := float64ToInt(tc.input)
			if got != tc.want {
				t.Errorf("float64ToInt(%v) = %d, want %d", tc.input, got, tc.want)
			}
		})
	}
}
