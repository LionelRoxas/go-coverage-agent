package stats

import (
	"errors"
	"math"
	"testing"
)

func winsorizeSlicesEqual(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("slice length mismatch: got %d, want %d", len(got), len(want))
	}
	const eps = 1e-9
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.IsInf(got[i], 0) || math.IsInf(want[i], 0) {
			if got[i] != want[i] {
				t.Fatalf("slice element %d mismatch: got %v, want %v", i, got[i], want[i])
			}
			continue
		}
		if math.Abs(got[i]-want[i]) > eps {
			t.Fatalf("slice element %d mismatch: got %v, want %v", i, got[i], want[i])
		}
	}
}

func TestWinsorize_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 0.1, ErrEmptyInput},
		{"negative percent", Float64Data{1, 2, 3}, -0.1, ErrBounds},
		{"percent too large", Float64Data{1, 2, 3}, 0.5, ErrBounds},
		{"percent NaN", Float64Data{1, 2, 3}, math.NaN(), ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := Winsorize(tc.input, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestWinsorize_Normal(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		percent float64
		want    []float64
	}{
		{"zero percent returns copy", Float64Data{2.5, -1.0, 4.0}, 0.0, []float64{2.5, -1.0, 4.0}},
		{"percent 0.2 clamps tails", Float64Data{5, 1, 9, 3, 7}, 0.2, []float64{5, 3, 7, 3, 7}},
		{"percent 0.4 clamps all to median", Float64Data{10, 20, 30, 40, 50}, 0.4, []float64{30, 30, 30, 30, 30}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Winsorize(tc.input, tc.percent)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			winsorizeSlicesEqual(t, got, tc.want)
			// ensure output is a new slice (modifying it does not affect input)
			if len(got) > 0 {
				orig := tc.input[0]
				got[0] = got[0] + 1
				if tc.input[0] != orig {
					t.Fatalf("output slice shares underlying array with input")
				}
			}
		})
	}
}

func TestFloat64Data_Winsorize_Delegates(t *testing.T) {
	input := Float64Data{8, 2, 6, 4}
	percent := 0.25
	direct, err1 := Winsorize(input, percent)
	if err1 != nil {
		t.Fatalf("direct call error: %v", err1)
	}
	method, err2 := input.Winsorize(percent)
	if err2 != nil {
		t.Fatalf("method call error: %v", err2)
	}
	winsorizeSlicesEqual(t, method, direct)
}
