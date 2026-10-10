package stats

import (
	"errors"
	"math"
	"testing"
)

func TestLogarithmicRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
		check   func(t *testing.T, got Series, err error)
	}{
		{
			name:    "empty input",
			s:       Series{},
			wantErr: EmptyInputErr,
		},
		{
			name:    "non-positive X",
			s:       Series{{X: 0, Y: 1}},
			wantErr: ErrBounds,
		},
		{
			name:    "variance zero (identical X)",
			s:       Series{{X: 2, Y: 1}, {X: 2, Y: 3}},
			wantErr: ErrBounds,
		},
		{
			name:    "valid regression matches points",
			s:       Series{{X: 1, Y: 2}, {X: math.E, Y: 4}},
			wantErr: nil,
			check: func(t *testing.T, got Series, err error) {
				if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
				if len(got) != len(Series{{X: 1, Y: 2}, {X: math.E, Y: 4}}) {
					t.Fatalf("unexpected length: %d", len(got))
				}
				for i, pt := range got {
					if math.Abs(pt.Y-Series{{X: 1, Y: 2}, {X: math.E, Y: 4}}[i].Y) > 1e-9 {
						t.Fatalf("point %d Y mismatch: got %v want %v", i, pt.Y, Series{{X: 1, Y: 2}, {X: math.E, Y: 4}}[i].Y)
					}
				}
			},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LogarithmicRegression(tc.s)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.check != nil {
				tc.check(t, got, err)
			}
		})
	}
}

func TestExponentialRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
		check   func(t *testing.T, got Series, err error)
	}{
		{
			name:    "empty input",
			s:       Series{},
			wantErr: EmptyInputErr,
		},
		{
			name:    "non-positive Y",
			s:       Series{{X: 1, Y: 0}},
			wantErr: ErrYCoord,
		},
		{
			name:    "variance zero (identical X)",
			s:       Series{{X: 5, Y: 1}, {X: 5, Y: 2}},
			wantErr: ErrBounds,
		},
		{
			name:    "valid regression matches points",
			s:       Series{{X: 0, Y: 1}, {X: 1, Y: math.E}},
			wantErr: nil,
			check: func(t *testing.T, got Series, err error) {
				if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
				if len(got) != 2 {
					t.Fatalf("unexpected length: %d", len(got))
				}
				for i, pt := range got {
					wantY := Series{{X: 0, Y: 1}, {X: 1, Y: math.E}}[i].Y
					if math.Abs(pt.Y-wantY) > 1e-9 {
						t.Fatalf("point %d Y mismatch: got %v want %v", i, pt.Y, wantY)
					}
				}
			},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ExponentialRegression(tc.s)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.check != nil {
				tc.check(t, got, err)
			}
		})
	}
}

func TestLinearRegression(t *testing.T) {
	cases := []struct {
		name    string
		s       Series
		wantErr error
		check   func(t *testing.T, got Series, err error)
	}{
		{
			name:    "empty input",
			s:       Series{},
			wantErr: EmptyInputErr,
		},
		{
			name:    "variance zero (identical X)",
			s:       Series{{X: 3, Y: 1}, {X: 3, Y: 4}},
			wantErr: ErrBounds,
		},
		{
			name:    "valid regression matches points",
			s:       Series{{X: 0, Y: 0}, {X: 1, Y: 2}},
			wantErr: nil,
			check: func(t *testing.T, got Series, err error) {
				if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
				if len(got) != 2 {
					t.Fatalf("unexpected length: %d", len(got))
				}
				expected := []float64{0, 2}
				for i, pt := range got {
					if math.Abs(pt.Y-expected[i]) > 1e-9 {
						t.Fatalf("point %d Y mismatch: got %v want %v", i, pt.Y, expected[i])
					}
				}
			},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := LinearRegression(tc.s)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.check != nil {
				tc.check(t, got, err)
			}
		})
	}
}
