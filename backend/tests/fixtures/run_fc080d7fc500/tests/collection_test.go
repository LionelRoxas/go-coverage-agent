package semver

import (
	"testing"
)

func TestCollection_Len(t *testing.T) {
	cases := []struct {
		name string
		col  Collection
		want int
	}{
		{name: "nil slice", col: nil, want: 0},
		{name: "empty slice", col: Collection{}, want: 0},
		{name: "three elements", col: Collection{&Version{major: 1}, &Version{major: 2}, &Version{major: 3}}, want: 3},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := tc.col.Len()
			if got != tc.want {
				t.Fatalf("Len() = %d, want %d", got, tc.want)
			}
		})
	}
}

func TestCollection_Less(t *testing.T) {
	v1 := &Version{major: 1}
	v2 := &Version{major: 2}
	v3 := &Version{major: 3}
	cases := []struct {
		name string
		col  Collection
		i, j int
		want bool
	}{
		{name: "less true", col: Collection{v1, v2}, i: 0, j: 1, want: true},
		{name: "less false", col: Collection{v2, v1}, i: 0, j: 1, want: false},
		{name: "equal false", col: Collection{v3, v3}, i: 0, j: 1, want: false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := tc.col.Less(tc.i, tc.j)
			if got != tc.want {
				t.Fatalf("Less(%d,%d) = %v, want %v", tc.i, tc.j, got, tc.want)
			}
		})
	}
}

func TestCollection_Swap(t *testing.T) {
	v1 := &Version{major: 1}
	v2 := &Version{major: 2}
	v3 := &Version{major: 3}
	col := Collection{v1, v2, v3}
	col.Swap(0, 2)
	expected := Collection{v3, v2, v1}
	for i := range expected {
		if col[i] != expected[i] {
			t.Fatalf("after Swap, index %d = %v, want %v", i, col[i], expected[i])
		}
	}
}
