package stats

import (
	"errors"
	"math"
	"testing"
)

func rollingApproxEqual(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	const eps = 1e-9
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > eps {
			t.Fatalf("at index %d: got %v, want %v", i, got[i], want[i])
		}
	}
}

func TestMovingAverage(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 3, nil, ErrEmptyInput},
		{"window too small", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"window too large", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"normal case", Float64Data{1, 2, 3, 4, 5}, 3, []float64{2, 3, 4}, nil},
		{"full window", Float64Data{10, 20, 30}, 3, []float64{20}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingAverage(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				rollingApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestMovingStdDev(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 2, nil, ErrEmptyInput},
		{"window too small", Float64Data{1, 2, 3}, 1, nil, ErrBounds},
		{"window too large", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"normal case", Float64Data{1, 2, 3, 4, 5}, 2, []float64{0.7071067811865476, 0.7071067811865476, 0.7071067811865476, 0.7071067811865476}, nil},
		{"full window", Float64Data{1, 2, 3, 4, 5}, 5, []float64{1.5811388300841898}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingStdDev(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				rollingApproxEqual(t, got, tc.want)
			}
		})
	}
}

func TestFloat64Data_MovingAverage(t *testing.T) {
	input := Float64Data{2, 4, 6, 8}
	window := 2
	// top‑level function expected result
	want, err := MovingAverage(input, window)
	if err != nil {
		t.Fatalf("setup error: %v", err)
	}
	got, err := input.MovingAverage(window)
	if err != nil {
		t.Fatalf("method returned error: %v", err)
	}
	rollingApproxEqual(t, got, want)
}

func TestFloat64Data_MovingStdDev(t *testing.T) {
	input := Float64Data{5, 7, 9, 11}
	window := 3
	want, err := MovingStdDev(input, window)
	if err != nil {
		t.Fatalf("setup error: %v", err)
	}
	got, err := input.MovingStdDev(window)
	if err != nil {
		t.Fatalf("method returned error: %v", err)
	}
	rollingApproxEqual(t, got, want)
}
