package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestClip_ErrorsAndClamping(t *testing.T) {
	tests := []struct {
		name     string
		input    Float64Data
		min, max float64
		want     []float64
		wantErr  error
	}{
		{"empty input", Float64Data{}, 0, 1, nil, ErrEmptyInput},
		{"min greater than max", Float64Data{1, 2}, 5, 3, nil, ErrBounds},
		{"clamp values", Float64Data{-1, 0.5, 2}, 0, 1, []float64{0, 0.5, 1}, nil},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Clip(tc.input, tc.min, tc.max)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil && !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestFloat64Data_Clip_ErrorsAndClamping(t *testing.T) {
	tests := []struct {
		name     string
		input    Float64Data
		min, max float64
		want     []float64
		wantErr  error
	}{
		{"empty input", Float64Data{}, 0, 1, nil, ErrEmptyInput},
		{"min greater than max", Float64Data{1, 2}, 5, 3, nil, ErrBounds},
		{"clamp values", Float64Data{-1, 0.5, 2}, 0, 1, []float64{0, 0.5, 1}, nil},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.input.Clip(tc.min, tc.max)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil && !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
