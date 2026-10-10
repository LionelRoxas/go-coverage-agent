package stats

import (
	"errors"
	"math"
	"testing"
)

func TestMovingAverage_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 1, nil, ErrEmptyInput},
		{"window zero", Float64Data{1, 2, 3}, 0, nil, ErrBounds},
		{"window too large", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"normal case", Float64Data{1, 2, 3, 4, 5}, 2, []float64{1.5, 2.5, 3.5, 4.5}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingAverage(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.want) {
					t.Fatalf("len mismatch: got %d want %d", len(got), len(tc.want))
				}
				for i := range got {
					if math.Abs(got[i]-tc.want[i]) > 1e-9 {
						t.Fatalf("at %d: got %v want %v", i, got[i], tc.want[i])
					}
				}
			}
		})
	}
}

func TestMovingStdDev_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		window  int
		want    []float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 2, nil, ErrEmptyInput},
		{"window one", Float64Data{1, 2, 3}, 1, nil, ErrBounds},
		{"window too large", Float64Data{1, 2, 3}, 4, nil, ErrBounds},
		{"normal case", Float64Data{1, 2, 3, 4, 5}, 2, []float64{math.Sqrt(0.5), math.Sqrt(0.5), math.Sqrt(0.5), math.Sqrt(0.5)}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MovingStdDev(tc.input, tc.window)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.want) {
					t.Fatalf("len mismatch: got %d want %d", len(got), len(tc.want))
				}
				for i := range got {
					if math.Abs(got[i]-tc.want[i]) > 1e-9 {
						t.Fatalf("at %d: got %v want %v", i, got[i], tc.want[i])
					}
				}
			}
		})
	}
}

func TestFloat64Data_MovingAverageWrapper(t *testing.T) {
	data := Float64Data{10, 20, 30, 40}
	got, err := data.MovingAverage(2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{15, 25, 35}
	if len(got) != len(want) {
		t.Fatalf("len mismatch: got %d want %d", len(got), len(want))
	}
	for i := range got {
		if math.Abs(got[i]-want[i]) > 1e-9 {
			t.Fatalf("at %d: got %v want %v", i, got[i], want[i])
		}
	}
}

func TestFloat64Data_MovingStdDevWrapper(t *testing.T) {
	data := Float64Data{10, 20, 30, 40}
	got, err := data.MovingStdDev(2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := math.Sqrt(50) // sqrt(((-5)^2+(5)^2))
	want := []float64{expected, expected, expected}
	if len(got) != len(want) {
		t.Fatalf("len mismatch: got %d want %d", len(got), len(want))
	}
	for i := range got {
		if math.Abs(got[i]-want[i]) > 1e-9 {
			t.Fatalf("at %d: got %v want %v", i, got[i], want[i])
		}
	}
}
