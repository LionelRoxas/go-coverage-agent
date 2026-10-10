package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestClip(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		min     float64
		max     float64
		want    []float64
		wantErr error
	}{
		{
			name:    "EmptyInput",
			input:   []float64{},
			min:     0,
			max:     1,
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "BoundsError",
			input:   []float64{1, 2, 3},
			min:     5,
			max:     2,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "Clamping",
			input:   []float64{-5, 0, 2.5, 5, 10},
			min:     0,
			max:     5,
			want:    []float64{0, 0, 2.5, 5, 5},
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := Clip(tc.input, tc.min, tc.max)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if len(got) != len(tc.want) {
					t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
				}
				if !reflect.DeepEqual(got, tc.want) {
					t.Fatalf("result mismatch: got %v, want %v", got, tc.want)
				}
			} else {
				if got != nil {
					t.Fatalf("expected nil slice on error, got %v", got)
				}
			}
		})
	}
}

func TestFloat64Data_Clip(t *testing.T) {
	// Reuse the same cases as TestClip to ensure forwarding works
	cases := []struct {
		name    string
		input   []float64
		min     float64
		max     float64
		want    []float64
		wantErr error
	}{
		{
			name:    "EmptyInput",
			input:   []float64{},
			min:     0,
			max:     1,
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "BoundsError",
			input:   []float64{1, 2, 3},
			min:     5,
			max:     2,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "Clamping",
			input:   []float64{-5, 0, 2.5, 5, 10},
			min:     0,
			max:     5,
			want:    []float64{0, 0, 2.5, 5, 5},
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.input)
			got, err := f.Clip(tc.min, tc.max)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil {
				if !reflect.DeepEqual(got, tc.want) {
					t.Fatalf("result mismatch: got %v, want %v", got, tc.want)
				}
			} else {
				if got != nil {
					t.Fatalf("expected nil slice on error, got %v", got)
				}
			}
		})
	}
}
