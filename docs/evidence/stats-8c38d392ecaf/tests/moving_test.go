package stats

import (
	"errors"
	"math"
	"testing"
)

func movingApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) || math.IsInf(b, 0) {
		return a == b
	}
	return math.Abs(a-b) <= eps
}

func movingSlicesApproxEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if !movingApproxEqual(a[i], b[i]) {
			return false
		}
	}
	return true
}

func TestMovingMax(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, 1, nil, ErrEmptyInput},
		{"WindowZero", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"WindowTooLarge", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"Normal", Float64Data{1, 3, 2, 5, 4}, 3, []float64{3, 5, 5}, nil},
		{"FullWindow", Float64Data{2, 1, 3}, 3, []float64{3}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMax(tc.input, tc.window)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesApproxEqual(got, tc.want) {
				t.Errorf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingMedian(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, 1, nil, ErrEmptyInput},
		{"WindowZero", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"WindowTooLarge", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"Normal", Float64Data{1, 3, 2, 5, 4}, 3, []float64{2, 3, 4}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMedian(tc.input, tc.window)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesApproxEqual(got, tc.want) {
				t.Errorf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingMin(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, 1, nil, ErrEmptyInput},
		{"WindowZero", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"WindowTooLarge", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"Normal", Float64Data{1, 3, 2, 5, 4}, 3, []float64{1, 2, 2}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMin(tc.input, tc.window)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesApproxEqual(got, tc.want) {
				t.Errorf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingSum(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"EmptyInput", Float64Data{}, 1, nil, ErrEmptyInput},
		{"WindowZero", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"WindowTooLarge", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"Normal", Float64Data{1, 3, 2, 5, 4}, 3, []float64{6, 10, 11}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingSum(tc.input, tc.window)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesApproxEqual(got, tc.want) {
				t.Errorf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_MovingMax(t *testing.T) {
	input := Float64Data{4, 2, 7, 1, 5}
	window := 2
	// Expected rolling max: [4,7,7,5]
	want := []float64{4, 7, 7, 5}
	got, err := input.MovingMax(window)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !movingSlicesApproxEqual(got, want) {
		t.Errorf("method result mismatch: got %v, want %v", got, want)
	}
}
