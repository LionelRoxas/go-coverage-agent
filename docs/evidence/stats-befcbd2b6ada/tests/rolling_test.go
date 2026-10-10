package stats

import (
	"errors"
	"math"
	"testing"
)

func rollingSlicesClose(a, b []float64, tol float64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if math.IsNaN(a[i]) && math.IsNaN(b[i]) {
			continue
		}
		if math.Abs(a[i]-b[i]) > tol {
			return false
		}
	}
	return true
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

func TestMovingAverage_Basic(t *testing.T) {
	input := Float64Data{1, 2, 3, 4}
	window := 2
	got, err := MovingAverage(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{1.5, 2.5, 3.5}
	if !rollingSlicesClose(got, want, 1e-9) {
		t.Fatalf("unexpected result: got %v want %v", got, want)
	}
}

func TestMovingStdDev_Errors(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		wantErr error
	}{
		{"empty input", Float64Data{}, 2, ErrEmptyInput},
		{"window too small", Float64Data{1, 2, 3}, 1, ErrBounds},
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

func TestMovingStdDev_Basic(t *testing.T) {
	input := Float64Data{1, 3, 5, 7}
	window := 2
	got, err := MovingStdDev(input, window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// For each pair, stddev = |x-y|/sqrt(2)
	sqrt2 := math.Sqrt2
	want := []float64{math.Abs(1-3) / sqrt2, math.Abs(3-5) / sqrt2, math.Abs(5-7) / sqrt2}
	if !rollingSlicesClose(got, want, 1e-9) {
		t.Fatalf("unexpected result: got %v want %v", got, want)
	}
}

func TestFloat64Data_MovingAverage(t *testing.T) {
	data := Float64Data{10, 20, 30, 40, 50}
	window := 3
	gotMethod, errMethod := data.MovingAverage(window)
	if errMethod != nil {
		t.Fatalf("method returned error: %v", errMethod)
	}
	gotFunc, errFunc := MovingAverage(data, window)
	if errFunc != nil {
		t.Fatalf("function returned error: %v", errFunc)
	}
	if !rollingSlicesClose(gotMethod, gotFunc, 1e-9) {
		t.Fatalf("method and function results differ: %v vs %v", gotMethod, gotFunc)
	}
}

func TestFloat64Data_MovingStdDev(t *testing.T) {
	data := Float64Data{2, 4, 6, 8, 10}
	window := 3
	gotMethod, errMethod := data.MovingStdDev(window)
	if errMethod != nil {
		t.Fatalf("method returned error: %v", errMethod)
	}
	gotFunc, errFunc := MovingStdDev(data, window)
	if errFunc != nil {
		t.Fatalf("function returned error: %v", errFunc)
	}
	if !rollingSlicesClose(gotMethod, gotFunc, 1e-9) {
		t.Fatalf("method and function results differ: %v vs %v", gotMethod, gotFunc)
	}
}
