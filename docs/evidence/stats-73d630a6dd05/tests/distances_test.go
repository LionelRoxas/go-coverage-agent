package stats

import (
	"errors"
	"math"
	"testing"
)

func distancesApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestChebyshevDistance(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		want    float64
		wantErr error
	}{
		{
			name: "normal case",
			x:    Float64Data{1, -2, 3},
			y:    Float64Data{4, -5, 0},
			want: 3,
		},
		{
			name:    "empty input triggers error",
			x:       Float64Data{},
			y:       Float64Data{1},
			wantErr: EmptyInputErr,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ChebyshevDistance(tc.x, tc.y)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesApproxEqual(got, tc.want) {
				t.Fatalf("distance = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestMinkowskiDistance(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		lambda  float64
		want    float64
		wantErr error
	}{
		{
			name:   "lambda 2 matches Euclidean",
			x:      Float64Data{1, 2},
			y:      Float64Data{4, 6},
			lambda: 2,
			// Euclidean distance sqrt((3)^2+(4)^2)=5
			want: 5,
		},
		{
			name:    "lambda 0 leads to Inf error",
			x:       Float64Data{0, 0},
			y:       Float64Data{2, 2},
			lambda:  0,
			wantErr: InfValue,
		},
		{
			name:    "size mismatch error",
			x:       Float64Data{1, 2, 3},
			y:       Float64Data{1, 2},
			lambda:  1,
			wantErr: SizeErr,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MinkowskiDistance(tc.x, tc.y, tc.lambda)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesApproxEqual(got, tc.want) {
				t.Fatalf("distance = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestEuclideanDistance(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		want    float64
		wantErr error
	}{
		{
			name: "simple case",
			x:    Float64Data{0, 0},
			y:    Float64Data{3, 4},
			want: 5,
		},
		{
			name:    "empty input error",
			x:       Float64Data{},
			y:       Float64Data{1},
			wantErr: EmptyInputErr,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := EuclideanDistance(tc.x, tc.y)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesApproxEqual(got, tc.want) {
				t.Fatalf("distance = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestManhattanDistance(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		want    float64
		wantErr error
	}{
		{
			name: "basic case",
			x:    Float64Data{1, -2, 3},
			y:    Float64Data{-1, 2, 0},
			// |2|+| -4|+|3| = 2+4+3 =9
			want: 9,
		},
		{
			name:    "size mismatch error",
			x:       Float64Data{1},
			y:       Float64Data{1, 2},
			wantErr: SizeErr,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ManhattanDistance(tc.x, tc.y)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !distancesApproxEqual(got, tc.want) {
				t.Fatalf("distance = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestValidateData(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		wantErr error
	}{
		{name: "both empty", x: Float64Data{}, y: Float64Data{}, wantErr: EmptyInputErr},
		{name: "first empty", x: Float64Data{}, y: Float64Data{1}, wantErr: EmptyInputErr},
		{name: "second empty", x: Float64Data{1}, y: Float64Data{}, wantErr: EmptyInputErr},
		{name: "size mismatch", x: Float64Data{1, 2}, y: Float64Data{1}, wantErr: SizeErr},
		{name: "valid data", x: Float64Data{1, 2}, y: Float64Data{3, 4}, wantErr: nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			err := validateData(tc.x, tc.y)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
			} else {
				if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
			}
		})
	}
}
