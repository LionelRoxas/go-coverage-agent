package stats

import (
	"errors"
	"math"
	"testing"
)

func movingSlicesClose(got, want []float64) bool {
	if len(got) != len(want) {
		return false
	}
	const eps = 1e-9
	for i := range got {
		if math.Abs(got[i]-want[i]) > eps {
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
		{"empty input", Float64Data{}, 3, nil, ErrEmptyInput},
		{"invalid window zero", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"invalid window too large", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"single window", Float64Data{5, 1, 3}, 3, []float64{5}, nil},
		{"multiple windows", Float64Data{1, 3, 2, 5, 4}, 3, []float64{3, 5, 5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMax(tc.input, tc.window)
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if !errors.Is(err, tc.wantErr) && err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesClose(got, tc.want) {
				t.Fatalf("unexpected result, got %v, want %v", got, tc.want)
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
		{"empty input", Float64Data{}, 3, nil, ErrEmptyInput},
		{"invalid window", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"single window", Float64Data{2, 4, 6}, 3, []float64{4}, nil},
		{"multiple windows", Float64Data{1, 3, 2, 5, 4}, 3, []float64{2, 3, 4}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMedian(tc.input, tc.window)
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if !errors.Is(err, tc.wantErr) && err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesClose(got, tc.want) {
				t.Fatalf("unexpected result, got %v, want %v", got, tc.want)
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
		{"empty input", Float64Data{}, 2, nil, ErrEmptyInput},
		{"invalid window", Float64Data{5, 1, 3}, 0, nil, ErrBounds},
		{"single window", Float64Data{7, 2, 9}, 3, []float64{2}, nil},
		{"multiple windows", Float64Data{1, 3, 2, 5, 4}, 3, []float64{1, 2, 2}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingMin(tc.input, tc.window)
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if !errors.Is(err, tc.wantErr) && err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesClose(got, tc.want) {
				t.Fatalf("unexpected result, got %v, want %v", got, tc.want)
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
		{"empty input", Float64Data{}, 1, nil, ErrEmptyInput},
		{"invalid window", Float64Data{1, 2}, 0, nil, ErrBounds},
		{"single window", Float64Data{2, 4, 6}, 3, []float64{12}, nil},
		{"multiple windows", Float64Data{1, 3, 2, 5, 4}, 3, []float64{6, 10, 11}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingSum(tc.input, tc.window)
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if !errors.Is(err, tc.wantErr) && err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesClose(got, tc.want) {
				t.Fatalf("unexpected result, got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_MovingMax(t *testing.T) {
	// Reuse cases from TestMovingMax to verify the method forwards correctly.
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 2, nil, ErrEmptyInput},
		{"invalid window", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"valid", Float64Data{4, 1, 7, 3}, 2, []float64{4, 7, 7}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.MovingMax(tc.window)
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if !errors.Is(err, tc.wantErr) && err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingSlicesClose(got, tc.want) {
				t.Fatalf("unexpected result, got %v, want %v", got, tc.want)
			}
		})
	}
}

func movingApproxEqual(got, want []float64) bool {
	if len(got) != len(want) {
		return false
	}
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > 1e-9 {
			return false
		}
	}
	return true
}

func TestMovingSum_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		window  int
		want    []float64
		wantErr bool
	}{
		{"normal", []float64{1, 2, 3, 4, 5}, 3, []float64{6, 9, 12}, false},
		{"empty", []float64{}, 3, nil, true},
		{"zero window", []float64{1, 2}, 0, nil, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).MovingSum(tc.window)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingApproxEqual(got, tc.want) {
				t.Fatalf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingMin_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		window  int
		want    []float64
		wantErr bool
	}{
		{"normal", []float64{5, 3, 8, 2, 7}, 2, []float64{3, 3, 2, 2}, false},
		{"empty", []float64{}, 2, nil, true},
		{"zero window", []float64{1, 2}, 0, nil, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).MovingMin(tc.window)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingApproxEqual(got, tc.want) {
				t.Fatalf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMovingMedian_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		window  int
		want    []float64
		wantErr bool
	}{
		{"normal", []float64{1, 3, 2, 6, 5}, 3, []float64{2, 3, 5}, false},
		{"empty", []float64{}, 3, nil, true},
		{"zero window", []float64{1, 2}, 0, nil, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).MovingMedian(tc.window)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !movingApproxEqual(got, tc.want) {
				t.Fatalf("result mismatch: got %v, want %v", got, tc.want)
			}
		})
	}
}
