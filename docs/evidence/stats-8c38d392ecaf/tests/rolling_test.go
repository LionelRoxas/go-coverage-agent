package stats

import (
	"errors"
	"math"
	"testing"
)

func rollingApproxEqual(t *testing.T, got, want []float64) {
	if len(got) != len(want) {
		t.Fatalf("slice length mismatch: got %d, want %d", len(got), len(want))
	}
	const eps = 1e-9
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if diff := math.Abs(got[i] - want[i]); diff > eps {
			t.Fatalf("value mismatch at index %d: got %v, want %v (diff %v)", i, got[i], want[i], diff)
		}
	}
}

func TestMovingAverage_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		wantErr error
	}{
		{"empty input", Float64Data{}, 1, ErrEmptyInput},
		{"window zero", Float64Data{1, 2, 3}, 0, ErrBounds},
		{"window too large", Float64Data{1, 2, 3}, 4, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := MovingAverage(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestMovingAverage_Normal(t *testing.T) {
	input := Float64Data{1, 2, 3, 4, 5}
	window := 3
	got, err := MovingAverage(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Expected means: [2,3,4]
	want := []float64{2, 3, 4}
	rollingApproxEqual(t, got, want)
}

func TestFloat64Data_MovingAverage_Delegates(t *testing.T) {
	input := Float64Data{10, 20, 30, 40}
	window := 2
	want, err := MovingAverage(input, window)
	if err != nil {
		t.Fatalf("unexpected error from function: %v", err)
	}
	got, err := input.MovingAverage(window)
	if err != nil {
		t.Fatalf("unexpected error from method: %v", err)
	}
	rollingApproxEqual(t, got, want)
}

func TestMovingStdDev_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		wantErr error
	}{
		{"empty input", Float64Data{}, 2, ErrEmptyInput},
		{"window one (too small)", Float64Data{1, 2, 3}, 1, ErrBounds},
		{"window too large", Float64Data{1, 2, 3}, 4, ErrBounds},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := MovingStdDev(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestMovingStdDev_Normal(t *testing.T) {
	input := Float64Data{1, 2, 3, 4}
	window := 2
	got, err := MovingStdDev(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Compute expected using StandardDeviationSample for each window
	want := make([]float64, 0, len(input)-window+1)
	for i := 0; i <= len(input)-window; i++ {
		s, _ := StandardDeviationSample(input[i : i+window])
		want = append(want, s)
	}
	rollingApproxEqual(t, got, want)
}

func TestFloat64Data_MovingStdDev_Delegates(t *testing.T) {
	input := Float64Data{5, 10, 15, 20, 25}
	window := 3
	want, err := MovingStdDev(input, window)
	if err != nil {
		t.Fatalf("unexpected error from function: %v", err)
	}
	got, err := input.MovingStdDev(window)
	if err != nil {
		t.Fatalf("unexpected error from method: %v", err)
	}
	rollingApproxEqual(t, got, want)
}
